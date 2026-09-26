/* Restrained GSAP motion layer. The interface remains complete without it. */
(() => {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const enabled = () => Boolean(window.gsap) && !reduced.matches;
  const animate = (targets, from, to) => {
    if (!enabled()) return;
    gsap.killTweensOf(targets);
    gsap.fromTo(targets, from, {duration: .24, ease: 'power3.out', clearProps: 'transform,opacity,filter', ...to});
  };

  window.CiteMotion = {
    ready() {
      if (!enabled()) return;
      gsap.timeline({defaults: {ease: 'power3.out'}})
        .from('.topbar', {y: -10, opacity: 0, duration: .28})
        .from('.page-heading > *', {y: 9, opacity: 0, duration: .28, stagger: .05}, '-=.12')
        .from('.process, .composer', {y: 8, opacity: 0, duration: .3, stagger: .07}, '-=.16');
    },
    stage(element) {
      if (!enabled() || !element) return;
      gsap.fromTo(element, {scale: .97, opacity: .72}, {scale: 1, opacity: 1, duration: .2, ease: 'power3.out', clearProps: 'transform,opacity'});
    },
    intents(elements) {
      animate(elements, {y: 5, opacity: 0}, {y: 0, opacity: 1, stagger: .035});
    },
    claims(elements) {
      animate(elements, {y: 9, opacity: 0, filter: 'blur(2px)'}, {y: 0, opacity: 1, filter: 'blur(0px)', stagger: .055, duration: .28});
    },
    evidence() {
      animate('#evidence > *', {x: 7, opacity: 0}, {x: 0, opacity: 1, stagger: .04});
    },
    trace(element) {
      animate(element, {x: -5, opacity: 0}, {x: 0, opacity: 1, duration: .18});
    },
    dialog(dialog) {
      animate(dialog, {y: 10, scale: .985, opacity: 0}, {y: 0, scale: 1, opacity: 1, duration: .25});
    },
    inspector(showing) {
      if (!enabled()) return;
      const targets = showing ? ['.sidebar', '.trace-pane'] : ['main'];
      animate(targets, {opacity: .65}, {opacity: 1, duration: .2});
    }
  };

  addEventListener('DOMContentLoaded', () => window.CiteMotion.ready(), {once: true});
})();
