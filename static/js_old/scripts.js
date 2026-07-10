(function($){
	jQuery(document).ready(function() {	

		// Scroll to Top
		jQuery('.scrolltotop').click(function(){
			jQuery('html').animate({'scrollTop' : '0px'}, 400);
			return false;
		});
		
		jQuery(window).scroll(function(){
			var upto = jQuery(window).scrollTop();
			if(upto > 500) {
				jQuery('.scrolltotop').fadeIn();
			} else {
				jQuery('.scrolltotop').fadeOut();
			}
		});

		//custom accordion
		jQuery(".accordion__title").click(function() {
			if ($(this).hasClass("active")) {
		      	$(this).removeClass("active").next().slideUp();
		    } else {
		      	$(".accordion__title").next().slideUp();
		      	$(".accordion__title").removeClass("active");
		      	$(this).addClass("active").next().slideDown();
		    }
		    return false;
		});


		

				
		
		
		
		
		
		
		
		
	});
})(jQuery);