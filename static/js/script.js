// Clean, optimized JavaScript with proper UX

// Initialize animations and interactions when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  // Initialize scroll-to-top functionality
  initScrollToTop();

  // Handle window resizing for responsive behavior
  handleResponsiveUpdates();

  // Initialize mobile hamburger menu
  initMobileMenu();
});

// Scroll to top functionality
function initScrollToTop() {
  const scrollTop = document.querySelector('.scrolltotop');
  if (!scrollTop) return;

  // Initialize with hidden state
  scrollTop.style.opacity = '0';
  scrollTop.style.pointerEvents = 'none';

  // Show/hide scroll to top button based on scroll position with throttle
  let scrollTimeout;
  window.addEventListener('scroll', function() {
    if (scrollTimeout) clearTimeout(scrollTimeout);
    
    scrollTimeout = setTimeout(function() {
      if (window.scrollY > 300) {
        scrollTop.style.opacity = '1';
        scrollTop.style.pointerEvents = 'auto';
      } else {
        scrollTop.style.opacity = '0';
        scrollTop.style.pointerEvents = 'none';
      }
    }, 10);
  }, { passive: true });

  // Smooth scroll to top
  scrollTop.addEventListener('click', function(e) {
    e.preventDefault();
    if (typeof gsap !== 'undefined') {
      gsap.to(window, {
        scrollTo: 0,
        duration: 0.8,
        ease: 'power3.inOut'
      });
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  });
}

// Mobile menu functionality
function initMobileMenu() {
  const menuButton = document.getElementById('menuButton');
  const mobileMenu = document.getElementById('mobileMenu');
  const closeMenuButton = document.getElementById('closeMenu');

  if (!menuButton || !mobileMenu) return;

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
    mobileMenu.classList.remove('hidden');
    mobileMenu.classList.add('active');
    menuButton.setAttribute('aria-expanded', 'true');
  }

  function closeMenu() {
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

// Handle responsive updates
function handleResponsiveUpdates() {
  let resizeTimer;
  window.addEventListener('resize', function() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function() {
      // Refresh scroll triggers on resize for proper mobile/desktop behavior
      if (typeof ScrollTrigger !== 'undefined') {
        ScrollTrigger.refresh();
      }
    }, 250);
  }, { passive: true });
}


