(function($){
	jQuery(document).ready(function() {

		// Smooth accordion functionality
		jQuery(".accordion__title").click(function(e) {
			e.preventDefault();
			var $title = $(this);
			var $body = $title.next('.accordion__body');
			var $allBodies = $('.accordion__body');
			var $allTitles = $('.accordion__title');

			// Close other accordion items
			$allTitles.not($title).removeClass("active");
			$allBodies.not($body).slideUp(300);

			// Toggle current item
			if ($title.hasClass("active")) {
				$title.removeClass("active");
				$body.slideUp(300);
			} else {
				$title.addClass("active");
				$body.slideDown(300);
			}
		});

		// Template Carousel with smooth transitions
		var $grid = $('.templates-strip__grid');
		var $track = $grid.find('.carousel-track');
		var $cards = $track.children('.template-card');
		var $prevBtn = $grid.find('.carousel-arrow:first-of-type');
		var $nextBtn = $grid.find('.carousel-arrow:last-of-type');
		var currentIndex = 0;
		var totalCards = $cards.length;
		var isAnimating = false;

		function getCardsToShow() {
			if (window.innerWidth < 576) return 1;
			if (window.innerWidth <= 991) return 2;
			return 3;
		}

		function getStepWidth() {
			if ($cards.length === 0) return 0;
			var cardWidth = $cards.first().outerWidth();
			var styles = window.getComputedStyle($track[0]);
			var gap = parseFloat(styles.columnGap || styles.gap) || 0;
			return cardWidth + gap;
		}

		function updateCarousel() {
			if (totalCards === 0) return;

			var cardsToShow = getCardsToShow();
			var maxIndex = Math.max(0, totalCards - cardsToShow);
			if (currentIndex > maxIndex) currentIndex = maxIndex;
			if (currentIndex < 0) currentIndex = 0;

			var offset = currentIndex * getStepWidth();

			isAnimating = true;
			$track.css({
				'transition': 'transform 0.35s ease-out',
				'transform': 'translateX(-' + offset + 'px)'
			});

			setTimeout(function() {
				isAnimating = false;
			}, 350);

			$prevBtn.prop('disabled', currentIndex === 0);
			$nextBtn.prop('disabled', currentIndex >= maxIndex);
		}

		$nextBtn.on('click', function(e) {
			e.preventDefault();
			if (isAnimating) return;
			var cardsToShow = getCardsToShow();
			if (currentIndex < totalCards - cardsToShow) {
				currentIndex++;
				updateCarousel();
			}
		});

		$prevBtn.on('click', function(e) {
			e.preventDefault();
			if (isAnimating) return;
			if (currentIndex > 0) {
				currentIndex--;
				updateCarousel();
			}
		});

		// Initialize carousel
		updateCarousel();

		// Handle window resize with debounce
		var resizeTimer;
		$(window).on('resize', function() {
			clearTimeout(resizeTimer);
			resizeTimer = setTimeout(function() {
				updateCarousel();
			}, 250);
		});

		// Keyboard navigation for carousel
		$(document).on('keydown', function(e) {
			if (e.key === 'ArrowLeft') {
				$prevBtn.trigger('click');
			} else if (e.key === 'ArrowRight') {
				$nextBtn.trigger('click');
			}
		});

	});

})(jQuery);


document.addEventListener('DOMContentLoaded',function(){

(function(){
  // ---- EDIT THIS ARRAY to change the steps' copy, tint color, and artwork ----
  const HIW_STEPS = [
    {
      title: "Upload Your Resume",
      desc: "Drop your existing resume file or paste the text directly into our editor. We accept PDF, DOC, DOCX, and plain text formats so you never have to reformat just to get started.",
      tint: "rgba(53,87,255,.08)",
      art: `
        <svg class="hiw-art" viewBox="0 0 300 220" fill="none">
          <rect x="90" y="30" width="120" height="150" rx="12" fill="#fff" stroke="rgba(96,119,180,.18)" stroke-width="2"/>
          <rect x="106" y="46" width="70" height="9" rx="4.5" fill="#182033" opacity=".85"/>
          <rect x="106" y="66" width="88" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <rect x="106" y="78" width="70" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <rect x="106" y="90" width="80" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <rect x="106" y="108" width="88" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <rect x="106" y="120" width="60" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <g class="hiw-floaty">
            <circle cx="150" cy="26" r="26" fill="#3557ff"/>
            <path d="M150 38V14M150 14l-9 9M150 14l9 9" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
          </g>
          <g>
            <rect x="18" y="146" width="46" height="26" rx="6" fill="#fff" stroke="rgba(96,119,180,.18)"/>
            <text x="41" y="163" font-size="10" font-weight="700" fill="#e5544d" text-anchor="middle" font-family="Inter, sans-serif">PDF</text>
          </g>
          <g>
            <rect x="18" y="176" width="46" height="26" rx="6" fill="#fff" stroke="rgba(96,119,180,.18)"/>
            <text x="41" y="193" font-size="10" font-weight="700" fill="#2f6fed" text-anchor="middle" font-family="Inter, sans-serif">DOC</text>
          </g>
          <g>
            <rect x="236" y="160" width="52" height="26" rx="6" fill="#fff" stroke="rgba(96,119,180,.18)"/>
            <text x="262" y="177" font-size="9" font-weight="700" fill="#7a5cf0" text-anchor="middle" font-family="Inter, sans-serif">DOCX</text>
          </g>
        </svg>`
    },
    {
      title: "AI Enhancement",
      desc: "Our advanced AI analyzes your content, improves language, adds impactful keywords, and optimizes structure for ATS compatibility.",
      tint: "rgba(53,87,255,.08)",
      art: `
        <svg class="hiw-art" viewBox="0 0 300 220" fill="none">
          <rect x="30" y="18" width="150" height="184" rx="12" fill="#fff" stroke="rgba(96,119,180,.18)" stroke-width="2"/>
          <rect x="46" y="34" width="70" height="9" rx="4.5" fill="#182033" opacity=".85"/>
          <rect x="46" y="54" width="118" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <rect x="46" y="66" width="90" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <rect x="46" y="86" width="118" height="6" rx="3" fill="#cfe4ff"/>
          <rect x="46" y="98" width="100" height="6" rx="3" fill="#cfe4ff"/>
          <rect x="46" y="118" width="118" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <rect x="46" y="130" width="70" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <g class="hiw-floaty">
            <rect x="150" y="120" width="128" height="72" rx="14" fill="#fff" stroke="#2f6fed" stroke-width="2"/>
            <circle cx="172" cy="142" r="10" fill="#2f6fed"/>
            <path d="M167 142l4 4 7-8" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
            <rect x="190" y="136" width="72" height="7" rx="3.5" fill="#2f6fed"/>
            <rect x="164" y="158" width="98" height="6" rx="3" fill="#8fa3ab"/>
            <rect x="164" y="170" width="70" height="14" rx="7" fill="#eaf2ff"/>
            <rect x="172" y="174" width="54" height="6" rx="3" fill="#2f6fed"/>
          </g>
          <circle class="hiw-floaty" cx="248" cy="46" r="4" fill="#2f6fed"/>
          <circle class="hiw-floaty" cx="264" cy="66" r="3" fill="#008573"/>
          <circle class="hiw-floaty" cx="232" cy="70" r="3" fill="#a78bfa"/>
        </svg>`
    },
    {
      title: "Get Results",
      desc: "Receive your enhanced resume with detailed analysis, improvement suggestions, and ATS score. Export and apply with confidence.",
      tint: "rgba(0,133,115,.08)",
      art: `
        <svg class="hiw-art" viewBox="0 0 300 220" fill="none">
          <rect x="20" y="14" width="130" height="176" rx="12" fill="#fff" stroke="#3557ff" stroke-width="2"/>
          <rect x="36" y="30" width="70" height="9" rx="4.5" fill="#182033" opacity=".85"/>
          <rect x="36" y="50" width="98" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <rect x="36" y="62" width="80" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <rect x="36" y="82" width="98" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <rect x="36" y="94" width="70" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <rect x="36" y="114" width="98" height="6" rx="3" fill="rgba(96,119,180,.18)"/>
          <circle cx="118" cy="20" r="12" fill="#3557ff"/>
          <path d="M113 20l3.5 3.5L124 15" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
          <g class="hiw-floaty">
            <circle cx="212" cy="90" r="44" fill="#fff" stroke="rgba(96,119,180,.18)" stroke-width="2"/>
            <circle cx="212" cy="90" r="44" fill="none" stroke="#3557ff" stroke-width="8" stroke-dasharray="207" stroke-dashoffset="35" stroke-linecap="round" transform="rotate(-90 212 90)"/>
            <text x="212" y="86" font-size="20" font-weight="800" fill="#182033" text-anchor="middle" font-family="Inter, sans-serif">94</text>
            <text x="212" y="102" font-size="9" font-weight="700" fill="#4a5670" text-anchor="middle" font-family="Inter, sans-serif">ATS SCORE</text>
          </g>
          <rect x="176" y="152" width="36" height="36" rx="8" fill="#fff" stroke="rgba(96,119,180,.18)"/>
          <rect x="184" y="160" width="20" height="4" rx="2" fill="#3557ff"/>
          <rect x="184" y="168" width="14" height="4" rx="2" fill="rgba(96,119,180,.18)"/>
          <rect x="184" y="176" width="16" height="4" rx="2" fill="rgba(96,119,180,.18)"/>
          <rect x="222" y="152" width="36" height="36" rx="8" fill="#fff" stroke="rgba(96,119,180,.18)"/>
          <rect x="230" y="160" width="20" height="4" rx="2" fill="#008573"/>
          <rect x="230" y="168" width="14" height="4" rx="2" fill="rgba(96,119,180,.18)"/>
          <rect x="230" y="176" width="16" height="4" rx="2" fill="rgba(96,119,180,.18)"/>
        </svg>`
    }
  ];

  const hiwWrap = document.getElementById('hiwWrap');
  const pinOuter = hiwWrap; // the outer element itself provides scroll room
  const pinInner = document.getElementById('hiwInner');
  const stepsEl = document.getElementById('hiwSteps');
  const artWrap = document.getElementById('hiwArtWrap');
  const panelBg = document.getElementById('hiwPanelBg');
  const panelGlow = document.getElementById('hiwPanelGlow');
  const panelEl = document.getElementById('hiwPanel');
  const headEl = document.getElementById('hiwHead');
  const gridEl = document.getElementById('hiwGrid');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let active = -1;

  stepsEl.innerHTML = `
    <div class="hiw-timeline-base" id="hiwTimelineBase"></div>
    <div class="hiw-timeline-fill" id="hiwTimelineFill"></div>
  ` + HIW_STEPS.map((s,i)=>`
    <div class="hiw-step" data-i="${i}">
      <div class="hiw-step-num">${i+1}</div>
      <div class="hiw-step-title">${s.title}</div>
      <div class="hiw-step-desc"><div class="hiw-step-desc-inner">
        <p>${s.desc}</p>
        <div class="hiw-progress-track"><div class="hiw-progress-fill" data-fill="${i}"></div></div>
      </div></div>
    </div>
  `).join('');

  const stepEls = [...stepsEl.querySelectorAll('.hiw-step')];
  const fillEls = [...stepsEl.querySelectorAll('.hiw-progress-fill')];
  const numEls = [...stepsEl.querySelectorAll('.hiw-step-num')];
  const timelineBase = document.getElementById('hiwTimelineBase');
  const timelineFill = document.getElementById('hiwTimelineFill');

  function measureTrack(){
    const containerRect = stepsEl.getBoundingClientRect();
    const firstRect = numEls[0].getBoundingClientRect();
    const lastRect = numEls[numEls.length - 1].getBoundingClientRect();
    const centerX = (firstRect.left + firstRect.width / 2) - containerRect.left;
    const top = (firstRect.top + firstRect.height / 2) - containerRect.top;
    const height = (lastRect.top + lastRect.height / 2) - containerRect.top - top;
    [timelineBase, timelineFill].forEach(el=>{
      el.style.left = `${centerX}px`;
      el.style.top = `${top}px`;
    });
    timelineBase.style.height = `${height}px`;
    return height;
  }

  function setActive(i){
    if(i === active) return;
    const dir = i > active ? 'up' : 'down';
    active = i;
    stepEls.forEach((el,idx)=> el.classList.toggle('hiw-active', idx === i));

    if(!reduceMotion){
      numEls[i].classList.remove('hiw-pop');
      void numEls[i].offsetWidth;
      numEls[i].classList.add('hiw-pop');
    }

    const outgoing = artWrap.querySelector('.hiw-art');
    if(outgoing){
      outgoing.classList.remove('hiw-show');
      outgoing.classList.add(dir === 'up' ? 'hiw-exit-up' : 'hiw-exit-down');
    }

    const temp = document.createElement('div');
    temp.innerHTML = HIW_STEPS[i].art;
    const incoming = temp.firstElementChild;
    incoming.classList.add(dir === 'up' ? 'hiw-exit-up' : 'hiw-exit-down');

    const swap = ()=>{
      artWrap.innerHTML = '';
      artWrap.appendChild(incoming);
      requestAnimationFrame(()=>{
        incoming.classList.remove('hiw-exit-up','hiw-exit-down');
        incoming.classList.add('hiw-show');
      });
    };
    if(outgoing && !reduceMotion){ setTimeout(swap, 260); } else { swap(); }

    panelBg.style.background = `radial-gradient(120% 120% at 15% 0%, ${HIW_STEPS[i].tint}, transparent 60%)`;
    panelGlow.style.background = HIW_STEPS[i].tint;
  }

  let trackHeight = 0;
  let isDesktop = window.matchMedia('(min-width:861px)').matches;

  function sizePinOuter(){
    if(isDesktop){
      pinOuter.style.height = `${(HIW_STEPS.length + 1) * 100}vh`;
    } else {
      pinOuter.style.height = 'auto';
    }
  }

  function clamp(v,min,max){ return Math.min(Math.max(v,min),max); }

  let ticking = false;
  function onScroll(){
    if(ticking) return;
    ticking = true;
    requestAnimationFrame(()=>{
      if(isDesktop){
        const rect = pinOuter.getBoundingClientRect();
        const scrollable = pinOuter.offsetHeight - window.innerHeight;
        const progress = clamp(scrollable > 0 ? -rect.top / scrollable : 0, 0, 1);

        const raw = progress * HIW_STEPS.length;
        const idx = clamp(Math.floor(raw), 0, HIW_STEPS.length - 1);
        const frac = clamp(raw - idx, 0, 1);

        fillEls.forEach((el,i)=>{
          const f = i < idx ? 1 : (i === idx ? frac : 0);
          el.style.width = `${f * 100}%`;
          el.classList.toggle('hiw-live', i === idx && f > 0.02 && f < 1);
        });

        setActive(idx);
        timelineFill.style.height = `${progress * trackHeight}px`;
      } else {
        if (HIW_STEPS.every((_, i) => stepEls[i] && !stepEls[i].classList.contains('hiw-touched'))) {
          setActive(0);
          fillEls.forEach((el,i)=> el.style.width = i === 0 ? '100%' : '0%');
        }
      }
      ticking = false;
    });
  }

  function onResize(){
    isDesktop = window.matchMedia('(min-width:861px)').matches;
    sizePinOuter();
    trackHeight = measureTrack();
    onScroll();
  }

  sizePinOuter();
  trackHeight = measureTrack();
  window.addEventListener('scroll', onScroll, {passive:true});
  window.addEventListener('resize', onResize);
  onScroll();

  stepEls.forEach(el=>{
    el.addEventListener('click', ()=>{
      const idx = parseInt(el.dataset.i);
      el.classList.add('hiw-touched');
      if(isDesktop){
        const scrollable = pinOuter.offsetHeight - window.innerHeight;
        const targetProgress = (idx + 0.5) / HIW_STEPS.length;
        const targetY = pinOuter.offsetTop + targetProgress * scrollable;
        window.scrollTo({top: targetY, behavior:'smooth'});
      } else {
        setActive(idx);
        fillEls.forEach((f,i)=> f.style.width = i <= idx ? '100%' : '0%');
      }
    });
  });

  const isFinePointer = window.matchMedia('(pointer: fine)').matches;
  if(isFinePointer && !reduceMotion){
    panelEl.addEventListener('mousemove', (e)=>{
      const rect = panelEl.getBoundingClientRect();
      const px = (e.clientX - rect.left) / rect.width - 0.5;
      const py = (e.clientY - rect.top) / rect.height - 0.5;
      panelEl.style.transform = `rotateX(${(-py * 4).toFixed(2)}deg) rotateY(${(px * 4).toFixed(2)}deg)`;
    });
    panelEl.addEventListener('mouseleave', ()=>{
      panelEl.style.transform = 'rotateX(0) rotateY(0)';
    });
  }

  if(isDesktop){
    const io = new IntersectionObserver((entries)=>{
      entries.forEach(entry=>{
        if(entry.isIntersecting) entry.target.classList.add('hiw-in');
      });
    },{threshold:0.2});
    io.observe(headEl);
    io.observe(gridEl);
  } else {
    headEl.classList.add('hiw-in');
    gridEl.classList.add('hiw-in');
  }
})();

});