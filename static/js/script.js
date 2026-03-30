// Performance Optimized JavaScript - Reduced execution time

// Debounce function for performance
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Throttle function for scroll events
function throttle(func, limit) {
  let inThrottle;
  return function () {
    const args = arguments;
    const context = this;
    if (!inThrottle) {
      func.apply(context, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  }
}

// Lazy loading for images - Only initialize when needed
function lazyLoadImages() {
  const images = document.querySelectorAll('img[data-src]');
  if (images.length === 0) return; // Early return if no lazy images

  const imageObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        img.src = img.dataset.src;
        img.classList.add('loaded');
        img.removeAttribute('data-src');
        observer.unobserve(img);
      }
    });
  });

  images.forEach(img => imageObserver.observe(img));
}

// Optimized scroll animation with Intersection Observer - Only when elements exist
function initScrollAnimations() {
  const animatedElements = document.querySelectorAll('[data-animate]');
  if (animatedElements.length === 0) return; // Early return if no animated elements

  const animationObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const element = entry.target;
        const animation = element.dataset.animate;
        element.classList.add(animation);
        animationObserver.unobserve(element);
      }
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  });

  animatedElements.forEach(element => animationObserver.observe(element));
}

// Mobile menu functionality - Essential, keep optimized
function initMobileMenu() {
  const menuButton = document.getElementById('menuButton');
  const mobileMenu = document.getElementById('mobileMenu');
  const closeMenuButton = document.getElementById('closeMenu');

  if (!menuButton || !mobileMenu) return;

  // Use passive event listeners for better performance
  menuButton.addEventListener('click', toggleMenu, { passive: true });

  if (closeMenuButton) {
    closeMenuButton.addEventListener('click', closeMenu, { passive: true });
  }

  // Close menu when clicking outside
  document.addEventListener('click', handleOutsideClick, { passive: true });

  // Auto-close when clicking a link inside the mobile menu
  try {
    const mobileLinks = mobileMenu.querySelectorAll('a');
    mobileLinks.forEach(link => {
      link.addEventListener('click', closeMenu, { passive: true });
    });
  } catch (_) { /* no-op */ }

  function openMenu() {
    // Ensure the menu is visible and animated into view
    mobileMenu.classList.remove('hidden');
    mobileMenu.classList.add('active');
    menuButton.setAttribute('aria-expanded', 'true');
  }

  function closeMenu() {
    // Hide and deactivate to match CSS expectations
    mobileMenu.classList.remove('active');
    mobileMenu.classList.add('hidden');
    menuButton.setAttribute('aria-expanded', 'false');
  }

  function toggleMenu() {
    const isOpen = !mobileMenu.classList.contains('hidden') && mobileMenu.classList.contains('active');
    if (isOpen) {
      closeMenu();
    } else {
      openMenu();
    }
  }

  function handleOutsideClick(event) {
    if (!mobileMenu.contains(event.target) && !menuButton.contains(event.target)) {
      closeMenu();
    }
  }
}

// FAQ functionality - Defer to after page load
function initFAQ() {
  const faqItems = document.querySelectorAll('.faq-item');
  if (faqItems.length === 0) return; // Early return if no FAQ items

  faqItems.forEach(item => {
    const question = item.querySelector('.faq-question');
    if (question) {
      question.addEventListener('click', toggleFAQ, { passive: true });
    }
  });

  function toggleFAQ(event) {
    const answer = event.target.nextElementSibling;
    if (answer && answer.classList.contains('faq-answer')) {
      answer.classList.toggle('active');
      event.target.classList.toggle('active');
    }
  }
}

// Cloud animation - Defer to after page load
function initCloudAnimation() {
  const cloudElements = document.querySelectorAll('.cloud');
  if (cloudElements.length === 0) return; // Early return if no cloud elements

  const cloudObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('animate');
        cloudObserver.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.5
  });

  cloudElements.forEach(cloud => cloudObserver.observe(cloud));
}

// Work together animations - Defer to after page load
function initWorkTogetherAnimations() {
  const workTogetherSection = document.querySelector('.work-together');
  if (!workTogetherSection) return; // Early return if section doesn't exist

  const workObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('animate');
        workObserver.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.5
  });

  workObserver.observe(workTogetherSection);
}

// Service Worker registration - Defer to after page load
function initServiceWorker() {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      // Delay service worker registration to reduce main-thread work
      setTimeout(() => {
        navigator.serviceWorker.register('/sw.js')
          .then(registration => {
            console.log('SW registered: ', registration);
          })
          .catch(registrationError => {
            console.log('SW registration failed: ', registrationError);
          });
      }, 2000); // Wait 2 seconds after page load
    });
  }
}

// Initialize only critical functionality when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
  // Only essential functionality that affects user interaction
  initMobileMenu();

  // Remove loading class immediately
  document.body.classList.remove('loading');
  document.body.classList.add('loaded');
});

// Defer non-critical functionality to after page load
window.addEventListener('load', function () {
  // Wait a bit to ensure page is fully rendered
  setTimeout(() => {
    // Initialize non-critical features
    initFAQ();
    initCloudAnimation();
    initWorkTogetherAnimations();

    // Initialize performance features
    initServiceWorker();

    // Initialize lazy loading and animations
    lazyLoadImages();
    initScrollAnimations();
  }, 1000); // Wait 1 second after page load
});

// Optimized scroll handling with throttling - Only if needed
let scrollHandlerInitialized = false;
function initScrollHandler() {
  if (scrollHandlerInitialized) return;

  const throttledScrollHandler = throttle(() => {
    // Any scroll-based functionality can go here
    // Currently optimized to do nothing unless needed
  }, 16); // ~60fps

  window.addEventListener('scroll', throttledScrollHandler, { passive: true });
  scrollHandlerInitialized = true;
}

// Initialize scroll handler only when user starts scrolling
let scrollInitTimeout;
window.addEventListener('scroll', () => {
  if (!scrollInitTimeout) {
    scrollInitTimeout = setTimeout(() => {
      initScrollHandler();
    }, 1000); // Wait 1 second of scrolling before initializing
  }
}, { passive: true });

// Preload critical resources - Only essential images
function preloadCriticalResources() {
  const criticalImages = [
    '/static/images/logo23_large.png'
  ];

  criticalImages.forEach(src => {
    const link = document.createElement('link');
    link.rel = 'preload';
    link.as = 'image';
    link.href = src;
    document.head.appendChild(link);
  });
}

// Initialize preloading only when needed
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', preloadCriticalResources);
} else {
  preloadCriticalResources();
}


