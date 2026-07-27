require('dotenv').config();
const express = require('express');
const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
const cors = require('cors');

const app = express();

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Store user balances (in a real app, this would be a database)
const users = new Map();
const transactions = [];

// Sample user data
users.set('user123', {
    id: 'user123',
    name: 'John Doe',
    email: 'john@example.com',
    balance: 1000.00, // USD
    transactions: []
});

// Create a payment intent for sending money
app.post('/api/create-payment', async (req, res) => {
    try {
        const { amount, currency = 'usd', description } = req.body;

        // Create a PaymentIntent with Stripe
        const paymentIntent = await stripe.paymentIntents.create({
            amount: Math.round(amount * 100), // Convert to cents
            currency: currency,
            description: description || 'Payment transfer',
            payment_method_types: ['card'],
        });

        res.json({
            clientSecret: paymentIntent.client_secret,
            paymentIntentId: paymentIntent.id
        });
    } catch (error) {
        console.error('Payment creation error:', error);
        res.status(500).json({ error: error.message });
    }
});

// Confirm payment (transfer money)
app.post('/api/confirm-payment', async (req, res) => {
    try {
        const { paymentIntentId, userId, recipientId, amount } = req.body;

        // Confirm the payment with Stripe
        const paymentIntent = await stripe.paymentIntents.confirm(paymentIntentId);

        if (paymentIntent.status === 'succeeded') {
            // In a real app, update your database here
            const user = users.get(userId);
            const recipient = users.get(recipientId);

            if (user && recipient) {
                // Deduct from sender
                user.balance -= amount;
                // Add to recipient
                recipient.balance += amount;

                // Record transaction
                const transaction = {
                    id: Date.now().toString(),
                    from: user.name,
                    to: recipient.name,
                    amount: amount,
                    timestamp: new Date().toISOString(),
                    status: 'completed'
                };

                transactions.push(transaction);
                user.transactions.push(transaction);
                recipient.transactions.push(transaction);

                res.json({
                    success: true,
                    transaction: transaction,
                    newBalance: user.balance
                });
            }
        } else {
            res.status(400).json({
                error: 'Payment failed',
                status: paymentIntent.status
            });
        }
    } catch (error) {
        console.error('Payment confirmation error:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get user balance
app.get('/api/balance/:userId', (req, res) => {
    const user = users.get(req.params.userId);
    if (user) {
        res.json({
            userId: user.id,
            name: user.name,
            balance: user.balance,
            transactions: user.transactions.slice(-10) // Last 10 transactions
        });
    } else {
        res.status(404).json({ error: 'User not found' });
    }
});

// Send money (internal transfer)
app.post('/api/send-money', (req, res) => {
    const { fromUserId, toUserId, amount, description } = req.body;

    const sender = users.get(fromUserId);
    const recipient = users.get(toUserId);

    if (!sender || !recipient) {
        return res.status(404).json({ error: 'User not found' });
    }

    if (sender.balance < amount) {
        return res.status(400).json({ error: 'Insufficient balance' });
    }

    // Process transfer
    sender.balance -= amount;
    recipient.balance += amount;

    const transaction = {
        id: Date.now().toString(),
        from: sender.name,
        to: recipient.name,
        amount: amount,
        description: description || 'Transfer',
        timestamp: new Date().toISOString(),
        status: 'completed'
    };

    transactions.push(transaction);
    sender.transactions.push(transaction);
    recipient.transactions.push(transaction);

    res.json({
        success: true,
        transaction: transaction,
        senderBalance: sender.balance,
        recipientBalance: recipient.balance
    });
});

// Get all users (for demo)
app.get('/api/users', (req, res) => {
    const userList = Array.from(users.values()).map(user => ({
        id: user.id,
        name: user.name,
        balance: user.balance
    }));
    res.json(userList);
});

// Health check
app.get('/api/health', (req, res) => {
    res.json({
        status: 'online',
        users: users.size,
        transactions: transactions.length
    });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`\n💰 Payment Platform Running!`);
    console.log(`📱 Open: http://localhost:${PORT}`);
    console.log(`💳 Real USD transactions with Stripe`);
    console.log(`\n📋 Demo Users:`);
    console.log(`  - John Doe (user123): $${users.get('user123').balance}`);
    console.log(`  - Add more users in the code\n`);
});