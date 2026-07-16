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

		function getCardWidth() {
			if ($cards.length === 0) return 0;
			return $cards.first().outerWidth(true);
		}

		function updateCarousel() {
			if (isAnimating || totalCards === 0) return;

			var cardsToShow = getCardsToShow();
			var cardWidth = getCardWidth();
			var offset = currentIndex * cardWidth;

			isAnimating = true;

			// Use CSS transitions for smooth animation
			$track.css({
				'transition': 'transform 0.3s ease-out',
				'transform': 'translateX(-' + offset + 'px)'
			});

			setTimeout(function() {
				isAnimating = false;
			}, 300);

			// Update button states
			$prevBtn.prop('disabled', currentIndex === 0).css('opacity', currentIndex === 0 ? 0.5 : 1);
			$nextBtn.prop('disabled', currentIndex >= totalCards - cardsToShow).css('opacity', currentIndex >= totalCards - cardsToShow ? 0.5 : 1);
		}

		$nextBtn.on('click', function(e) {
			e.preventDefault();
			var cardsToShow = getCardsToShow();
			if (currentIndex < totalCards - cardsToShow) {
				currentIndex++;
				updateCarousel();
			}
		});

		$prevBtn.on('click', function(e) {
			e.preventDefault();
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
				var cardsToShow = getCardsToShow();
				if (currentIndex > totalCards - cardsToShow) {
					currentIndex = Math.max(0, totalCards - cardsToShow);
				}
				updateCarousel();
			}, 250);
		});

		// Keyboard navigation for carousel
		$(document).on('keydown', function(e) {
			if (e.key === 'ArrowLeft') {
				$prevBtn.click();
			} else if (e.key === 'ArrowRight') {
				$nextBtn.click();
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
      desc: "Paste in a job description if you want tailored results, then drag and drop your PDF, DOC, or DOCX file — up to 10MB. Everything is SSL encrypted and privacy protected.",
      tint: "rgba(53,87,255,.08)",
      art: `
        <svg class="hiw-art" viewBox="0 0 300 200" fill="none">
          <rect x="10" y="6" width="280" height="188" rx="14" fill="#fff" stroke="rgba(96,119,180,.18)" stroke-width="2"/>
          <rect x="24" y="20" width="10" height="10" rx="2" fill="#3557ff"/>
          <text x="40" y="29" font-size="9" font-weight="700" fill="#182033" font-family="Inter, sans-serif">Job Description (Optional)</text>
          <rect x="24" y="36" width="252" height="26" rx="6" fill="var(--hiw-wash)" stroke="rgba(96,119,180,.18)"/>
          <text x="32" y="52" font-size="7" fill="#9aa5c0" font-family="Inter, sans-serif">Paste job description…</text>
          <rect x="24" y="72" width="10" height="10" rx="2" fill="#3557ff"/>
          <text x="40" y="81" font-size="9" font-weight="700" fill="#182033" font-family="Inter, sans-serif">Submit Your Resume</text>
          <rect x="24" y="90" width="252" height="68" rx="10" fill="var(--hiw-wash)" stroke="#3557ff" stroke-width="2" stroke-dasharray="7 6" class="hiw-dash"/>
          <g class="hiw-floaty">
            <circle cx="150" cy="112" r="14" fill="#dbe6ff"/>
            <path d="M150 119v-14m0 0l-6 6m6-6l6 6" stroke="#3557ff" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
          </g>
          <text x="150" y="138" font-size="9" font-weight="700" fill="#3557ff" text-anchor="middle" font-family="Inter, sans-serif">Click to upload</text>
          <text x="150" y="148" font-size="7" fill="#8790ab" text-anchor="middle" font-family="Inter, sans-serif">or drag and drop your resume</text>
          <text x="118" y="155" font-size="6.5" font-weight="700" fill="#e5544d" text-anchor="middle" font-family="Inter, sans-serif">PDF</text>
          <text x="150" y="155" font-size="6.5" font-weight="700" fill="#2f6fed" text-anchor="middle" font-family="Inter, sans-serif">DOC</text>
          <text x="184" y="155" font-size="6.5" font-weight="700" fill="#7a5cf0" text-anchor="middle" font-family="Inter, sans-serif">DOCX</text>
          <rect x="24" y="168" width="252" height="20" rx="10" fill="url(#hiwBtnGrad1)"/>
          <text x="150" y="181" font-size="8.5" font-weight="700" fill="#fff" text-anchor="middle" font-family="Inter, sans-serif">✦ Enhance My Resume Now</text>
          <defs>
            <linearGradient id="hiwBtnGrad1" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stop-color="#3557ff"/>
              <stop offset="1" stop-color="#008573"/>
            </linearGradient>
          </defs>
        </svg>`
    },
    {
      title: "AI Enhancement",
      desc: "Our AI reads your resume, finds the useful information, and rewrites it for clarity and ATS compatibility — processing usually finishes in under 30 seconds.",
      tint: "rgba(53,87,255,.08)",
      art: `
        <svg class="hiw-art" viewBox="0 0 300 200" fill="none">
          <rect x="10" y="6" width="280" height="188" rx="14" fill="var(--hiw-wash)"/>
          <rect x="46" y="26" width="208" height="150" rx="14" fill="#fff" stroke="rgba(96,119,180,.18)" stroke-width="2"/>
          <rect x="90" y="40" width="120" height="18" rx="9" fill="#eaf2ff"/>
          <text x="150" y="52" font-size="7.5" font-weight="700" fill="#3557ff" text-anchor="middle" font-family="Inter, sans-serif">Finding useful information…</text>
          <g class="hiw-floaty">
            <rect x="132" y="66" width="30" height="38" rx="5" fill="#fff" stroke="#3557ff" stroke-width="2"/>
            <rect x="138" y="76" width="18" height="3" rx="1.5" fill="rgba(53,87,255,.4)"/>
            <rect x="138" y="83" width="18" height="3" rx="1.5" fill="rgba(53,87,255,.4)"/>
            <rect x="138" y="90" width="12" height="3" rx="1.5" fill="rgba(53,87,255,.4)"/>
            <circle cx="168" cy="98" r="9" fill="#fff" stroke="#008573" stroke-width="2.4"/>
            <line x1="174" y1="104" x2="180" y2="110" stroke="#008573" stroke-width="2.4" stroke-linecap="round"/>
          </g>
          <text x="150" y="124" font-size="10" font-weight="800" fill="#182033" text-anchor="middle" font-family="Inter, sans-serif">Enhancing your resume</text>
          <text x="150" y="136" font-size="8" fill="#4a5670" text-anchor="middle" font-family="Inter, sans-serif">Optimizing for ATS…</text>
          <rect x="66" y="146" width="168" height="7" rx="3.5" fill="rgba(96,119,180,.15)"/>
          <rect x="66" y="146" width="26" height="7" rx="3.5" fill="#3557ff" class="hiw-grow"/>
          <text x="150" y="164" font-size="7.5" font-weight="700" fill="#4a5670" text-anchor="middle" font-family="Inter, sans-serif">15% complete</text>
          <text x="150" y="176" font-size="6.5" fill="#8790ab" text-anchor="middle" font-family="Inter, sans-serif">Your data is processed securely</text>
        </svg>`
    },
    {
      title: "Get Your Results",
      desc: "See your ATS score, how you compare to other applicants, a full category breakdown, and a side-by-side before-and-after — then pick a template and export.",
      tint: "rgba(0,133,115,.08)",
      art: `
        <svg class="hiw-art" viewBox="0 0 300 200" fill="none">
          <rect x="10" y="6" width="280" height="188" rx="14" fill="#fff" stroke="rgba(96,119,180,.18)" stroke-width="2"/>
          <text x="26" y="26" font-size="8" font-weight="700" fill="#182033" font-family="Inter, sans-serif">Score</text>
          <g class="hiw-floaty">
            <path d="M26 78 A38 38 0 0 1 102 78" stroke="url(#hiwGaugeGrad)" stroke-width="8" fill="none" stroke-linecap="round"/>
            <line x1="64" y1="78" x2="64" y2="46" stroke="#182033" stroke-width="2.4" stroke-linecap="round" transform="rotate(46 64 78)"/>
            <circle cx="64" cy="78" r="3.5" fill="#182033"/>
          </g>
          <text x="64" y="98" font-size="17" font-weight="800" fill="#182033" text-anchor="middle" font-family="Inter, sans-serif">74</text>
          <text x="64" y="110" font-size="7.5" font-weight="700" fill="#008573" text-anchor="middle" font-family="Inter, sans-serif">Good</text>

          <text x="150" y="26" font-size="8" font-weight="700" fill="#182033" font-family="Inter, sans-serif">How You Compare</text>
          <text x="150" y="46" font-size="16" font-weight="800" fill="#182033" font-family="Inter, sans-serif">74<tspan font-size="9">%</tspan></text>
          <text x="150" y="56" font-size="6.5" fill="#8790ab" font-family="Inter, sans-serif">Percentile Rank</text>
          <rect x="150" y="66" width="120" height="6" rx="3" fill="url(#hiwGaugeGrad2)"/>
          <g class="hiw-pulse">
            <rect x="228" y="60" width="20" height="12" rx="6" fill="#008573"/>
            <text x="238" y="69" font-size="6" font-weight="700" fill="#fff" text-anchor="middle" font-family="Inter, sans-serif">You</text>
          </g>

          <g font-family="Inter, sans-serif">
            <rect x="26" y="128" width="118" height="24" rx="8" fill="var(--hiw-wash)" stroke="rgba(96,119,180,.18)"/>
            <text x="36" y="143" font-size="8" font-weight="700" fill="#182033">Content</text>
            <rect x="98" y="134" width="36" height="14" rx="7" fill="#eaf2ff"/>
            <text x="116" y="144" font-size="7.5" font-weight="800" fill="#3557ff" text-anchor="middle">70</text>

            <rect x="150" y="128" width="60" height="24" rx="8" fill="var(--hiw-wash)" stroke="rgba(96,119,180,.18)"/>
            <text x="158" y="143" font-size="8" font-weight="700" fill="#182033">Format</text>
            <text x="196" y="144" font-size="7.5" font-weight="800" fill="#008573" text-anchor="middle">82</text>

            <rect x="216" y="128" width="66" height="24" rx="8" fill="var(--hiw-wash)" stroke="rgba(96,119,180,.18)"/>
            <text x="224" y="143" font-size="7" font-weight="700" fill="#182033">Optimize</text>
            <text x="268" y="144" font-size="7.5" font-weight="800" fill="#008573" text-anchor="middle">76</text>
          </g>

          <rect x="26" y="160" width="256" height="24" rx="8" fill="#eaf7f4"/>
          <circle cx="38" cy="172" r="6" fill="#008573"/>
          <path d="M35 172l2 2 4-4" stroke="#fff" stroke-width="1.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
          <text x="50" y="175" font-size="7.5" font-weight="600" fill="#182033" font-family="Inter, sans-serif">Enhanced keywords, formatting &amp; ATS readiness</text>

          <defs>
            <linearGradient id="hiwGaugeGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stop-color="#e5544d"/>
              <stop offset="0.5" stop-color="#f5a623"/>
              <stop offset="1" stop-color="#008573"/>
            </linearGradient>
            <linearGradient id="hiwGaugeGrad2" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stop-color="#e5544d"/>
              <stop offset="0.5" stop-color="#f5a623"/>
              <stop offset="1" stop-color="#008573"/>
            </linearGradient>
          </defs>
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
