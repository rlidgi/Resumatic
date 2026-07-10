// Clean, optimized JavaScript with proper UX

// Initialize animations and interactions when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  // Initialize scroll-to-top functionality
  initScrollToTop();
  
  // Handle window resizing for responsive behavior
  handleResponsiveUpdates();
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


