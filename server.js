const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const cors = require('cors');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
    cors: {
        origin: "*",
        methods: ["GET", "POST"]
    },
    transports: ['websocket', 'polling']
});

// Middleware
app.use(cors());
app.use(express.static(path.join(__dirname, 'public')));

// Store users and messages
const users = new Map();
const messages = [];
const MAX_MESSAGES = 500;

io.on('connection', (socket) => {
    console.log(`✅ User connected: ${socket.id}`);

    // Send chat history
    socket.emit('chat history', messages.slice(-50));

    // User joins
    socket.on('user join', (username) => {
        const user = {
            id: socket.id,
            username: username.trim() || 'Anonymous',
            joinedAt: new Date()
        };
        
        users.set(socket.id, user);
        
        io.emit('user joined', {
            user,
            users: Array.from(users.values())
        });
        
        console.log(`👤 ${user.username} joined the chat (${users.size} online)`);
    });

    // New message
    socket.on('chat message', (data) => {
        const user = users.get(socket.id);
        if (!user) return;

        const message = {
            id: Date.now().toString(36) + Math.random().toString(36).substr(2, 5),
            userId: socket.id,
            username: user.username,
            message: data.message.trim().slice(0, 500),
            timestamp: new Date(),
            type: 'message'
        };

        messages.push(message);
        
        if (messages.length > MAX_MESSAGES) {
            messages.splice(0, messages.length - MAX_MESSAGES);
        }

        io.emit('chat message', message);
    });

    // Typing indicator
    socket.on('typing', (isTyping) => {
        const user = users.get(socket.id);
        if (user) {
            socket.broadcast.emit('user typing', {
                userId: socket.id,
                username: user.username,
                isTyping
            });
        }
    });

    // Private message
    socket.on('private message', ({ targetId, message }) => {
        const sender = users.get(socket.id);
        const recipient = users.get(targetId);
        
        if (sender && recipient) {
            const privateMsg = {
                id: Date.now().toString(36) + Math.random().toString(36).substr(2, 5),
                from: sender.username,
                to: recipient.username,
                message: message.trim().slice(0, 500),
                timestamp: new Date(),
                type: 'private'
            };
            
            io.to(targetId).emit('private message', privateMsg);
            socket.emit('private message sent', privateMsg);
        }
    });

    // Disconnect
    socket.on('disconnect', () => {
        const user = users.get(socket.id);
        if (user) {
            users.delete(socket.id);
            io.emit('user left', {
                userId: socket.id,
                username: user.username,
                users: Array.from(users.values())
            });
            console.log(`👋 ${user.username} left the chat (${users.size} online)`);
        }
    });

    socket.on('error', (error) => {
        console.error(`❌ Socket error for ${socket.id}:`, error);
    });
});

// Health check
app.get('/health', (req, res) => {
    res.json({
        status: 'ok',
        users: users.size,
        messages: messages.length,
        timestamp: new Date()
    });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, '0.0.0.0', () => {
    console.log(`🚀 Chat server running on http://localhost:${PORT}`);
    console.log(`📊 Health check: http://localhost:${PORT}/health`);
    console.log(`👥 Ready to accept connections`);
});