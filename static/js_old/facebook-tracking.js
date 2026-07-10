// Facebook Ad Tracking Script for Resumatic AI
// This script enhances tracking for Facebook ad performance

(function () {
    'use strict';

    // Initialize Facebook Pixel tracking if Facebook Pixel ID is provided
    const FACEBOOK_PIXEL_ID = ''; // Add your Facebook Pixel ID here

    // Enhanced analytics tracking
    const ResumaticAnalytics = {
        // Track page views with enhanced attribution
        trackPageView: function () {
            // Get URL parameters
            const urlParams = new URLSearchParams(window.location.search);
            const utmSource = urlParams.get('utm_source');
            const utmMedium = urlParams.get('utm_medium');
            const utmCampaign = urlParams.get('utm_campaign');

            // Check if this is a Facebook ad visit
            const isFacebookAd = utmSource && (
                utmSource.toLowerCase().includes('facebook') ||
                utmSource.toLowerCase().includes('fb')
            );

            // Track to our internal analytics
            this.sendTrackingData('page_view', {
                utm_source: utmSource,
                utm_medium: utmMedium,
                utm_campaign: utmCampaign,
                is_facebook_ad: isFacebookAd,
                page_url: window.location.href,
                referrer: document.referrer,
                timestamp: new Date().toISOString()
            });

            // If Facebook Pixel is configured, track there too
            if (FACEBOOK_PIXEL_ID && typeof fbq !== 'undefined') {
                fbq('track', 'PageView');
            }

            console.log('📊 Resumatic Analytics: Page view tracked', {
                source: utmSource || 'direct',
                campaign: utmCampaign || 'none',
                is_facebook_ad: isFacebookAd
            });
        },

        // Track resume submissions (conversions)
        trackResumeSubmission: function (conversionType = 'resume_upload') {
            const urlParams = new URLSearchParams(window.location.search);

            this.sendTrackingData('conversion', {
                conversion_type: conversionType,
                utm_source: urlParams.get('utm_source'),
                utm_medium: urlParams.get('utm_medium'),
                utm_campaign: urlParams.get('utm_campaign'),
                page_url: window.location.href,
                timestamp: new Date().toISOString()
            });

            // Track Facebook conversion if pixel is available
            if (FACEBOOK_PIXEL_ID && typeof fbq !== 'undefined') {
                fbq('track', 'Lead', {
                    content_name: 'Resume Enhancement',
                    content_category: 'AI Services'
                });
            }

            console.log('🎯 Resumatic Analytics: Conversion tracked', conversionType);
        },

        // Send tracking data to our backend
        sendTrackingData: function (eventType, data) {
            fetch('/api/track', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    event_type: eventType,
                    data: data
                })
            }).catch(error => {
                console.warn('Analytics tracking failed:', error);
            });
        },

        // Initialize tracking
        init: function () {
            // Track page view on load
            this.trackPageView();

            // Track resume form submissions
            const resumeForm = document.querySelector('form[action*="revise_resume"]');
            if (resumeForm) {
                resumeForm.addEventListener('submit', () => {
                    this.trackResumeSubmission('resume_submission');

                    // Send conversion event to backend
                    this.sendTrackingData('conversion', {
                        conversion_type: 'resume_submission',
                        page_url: window.location.href,
                        timestamp: new Date().toISOString()
                    });
                });
            }            // Track file uploads
            const fileInputs = document.querySelectorAll('input[type="file"]');
            fileInputs.forEach(input => {
                input.addEventListener('change', (e) => {
                    if (e.target.files.length > 0) {
                        this.trackResumeSubmission('file_upload');
                    }
                });
            });

            // Track newsletter signups
            const subscribeForm = document.querySelector('form[action*="subscribe"]');
            if (subscribeForm) {
                subscribeForm.addEventListener('submit', () => {
                    this.trackResumeSubmission('newsletter_signup');
                });
            }
        }
    };

    // Facebook Pixel initialization (if ID is provided)
    if (FACEBOOK_PIXEL_ID) {
        !function (f, b, e, v, n, t, s) {
            if (f.fbq) return; n = f.fbq = function () {
                n.callMethod ?
                n.callMethod.apply(n, arguments) : n.queue.push(arguments)
            };
            if (!f._fbq) f._fbq = n; n.push = n; n.loaded = !0; n.version = '2.0';
            n.queue = []; t = b.createElement(e); t.async = !0;
            t.src = v; s = b.getElementsByTagName(e)[0];
            s.parentNode.insertBefore(t, s)
        }(window, document, 'script',
            'https://connect.facebook.net/en_US/fbevents.js');

        fbq('init', FACEBOOK_PIXEL_ID);
        console.log('📘 Facebook Pixel initialized:', FACEBOOK_PIXEL_ID);
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => ResumaticAnalytics.init());
    } else {
        ResumaticAnalytics.init();
    }

    // Make analytics available globally for manual tracking
    window.ResumaticAnalytics = ResumaticAnalytics;

})();

// Usage examples:
// ResumaticAnalytics.trackResumeSubmission('custom_event');
// ResumaticAnalytics.trackPageView();
