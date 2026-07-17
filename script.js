// ===== MOBILE HAMBURGER MENU =====
const hamburger = document.getElementById('hamburger');
const nav = document.querySelector('.nav');

hamburger.addEventListener('click', () => {
    hamburger.classList.toggle('active');
    nav.classList.toggle('open');
});

// Close menu on link click (mobile)
document.querySelectorAll('.nav ul li a').forEach(link => {
    link.addEventListener('click', () => {
        hamburger.classList.remove('active');
        nav.classList.remove('open');
    });
});

// ===== ACTIVE NAV LINK SCROLLSPY =====
const sections = document.querySelectorAll('section[id]');
const navLinks = document.querySelectorAll('.nav ul li a');

window.addEventListener('scroll', () => {
    let current = 'home';
    sections.forEach(section => {
        const top = section.offsetTop - 150;
        if (window.scrollY >= top) {
            current = section.getAttribute('id');
        }
    });

    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === `#${current}`) {
            link.classList.add('active');
        }
    });
});

// ===== SMOOTH SCROLL FOR NAV LINKS =====
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            e.preventDefault();
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// ===== FLOATING CARD ANIMATION ON SCROLL =====
const floatingCards = document.querySelectorAll('.floating-card');

const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

floatingCards.forEach(card => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(20px)';
    card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(card);
});

// ===== STATS COUNTER ANIMATION =====
const stats = document.querySelectorAll('.stat h3');

const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const text = entry.target.textContent;
            const number = parseInt(text.replace(/[^0-9]/g, ''));
            if (!isNaN(number)) {
                let current = 0;
                const increment = Math.ceil(number / 60);
                const timer = setInterval(() => {
                    current += increment;
                    if (current >= number) {
                        entry.target.textContent = text;
                        clearInterval(timer);
                    } else {
                        entry.target.textContent = current + '+';
                    }
                }, 25);
            }
            counterObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.5 });

stats.forEach(stat => counterObserver.observe(stat));

// ===== WHATSAPP CLICK TRACKING (Optional) =====
document.querySelectorAll('a[href*="wa.me"]').forEach(link => {
    link.addEventListener('click', function() {
        console.log('WhatsApp clicked:', this.href);
        // You can add analytics tracking here
    });
});

// ===== CONSOLE WELCOME =====
console.log('%c❤️ Real Giving - Helping People Change Lives', 
    'font-size: 20px; font-weight: bold; color: #25D366;');
console.log('%c📞 WhatsApp: +234 913 375 0885', 
    'font-size: 14px; color: #075E54;');