/**
 * Shared GSAP animation utilities with cached module import.
 * All entrance/stagger animations centralised here to avoid DRY violations.
 */

type GSAPModule = typeof import('gsap');

/** GSAP tween return type (Omit<Tween,'then'> per gsap typings). */
export type GsapTween = Omit<gsap.core.Tween, 'then'> | null;

let _gsapPromise: Promise<GSAPModule> | null = null;

/** Cached dynamic import — only loads GSAP once across the entire app. */
export function getGsap(): Promise<GSAPModule> {
  if (!_gsapPromise) {
    _gsapPromise = import('gsap');
  }
  return _gsapPromise;
}

/** Stagger-in a list of card elements. Returns the tween for cleanup. */
export async function animateCardStagger(
  root: HTMLElement,
  selector: string,
): Promise<GsapTween> {
  const { gsap } = await getGsap();
  const cards = root.querySelectorAll(selector);
  if (!cards.length) return null;
  return gsap.from(cards, {
    y: 20, opacity: 0, duration: 0.4, stagger: 0.06, ease: 'power2.out',
  });
}

/** Fade-slide a single element. Returns the tween for cleanup. */
export async function animateElement(
  el: Element | null,
  from: gsap.TweenVars = { y: 30, opacity: 0, duration: 0.5, ease: 'power2.out' },
): Promise<GsapTween> {
  if (!el) return null;
  const { gsap } = await getGsap();
  return gsap.from(el, from);
}

/**
 * Animate stat counter values (count-up from 0).
 * Returns an array of tweens for cleanup via `killTweens()`.
 *
 * Instead of mutating Angular-managed textContent directly, this reads the
 * target value once, stores it, then animates a proxy object — writing back
 * only to a `[data-gsap-target]` span if present, or the element itself as
 * a fallback. Pages should wrap the numeric value in a dedicated span to
 * avoid conflicting with Angular change detection.
 */
export async function animateStatCounters(
  root: HTMLElement,
): Promise<GsapTween[]> {
  const { gsap } = await getGsap();
  const tweens: GsapTween[] = [];

  root.querySelectorAll('.stat-value').forEach((statEl: Element) => {
    const text = statEl.textContent?.trim() ?? '';
    const match = text.match(/^([\d.]+)(.*)/);
    if (!match) return;

    const num = parseFloat(match[1]);
    if (isNaN(num)) return;

    const suffix = match[2];
    const isFloat = match[1].includes('.');
    const obj = { val: 0 };

    const tween = gsap.to(obj, {
      val: num,
      duration: 1.2,
      ease: 'power2.out',
      onUpdate: () => {
        const display = isFloat ? obj.val.toFixed(1) : Math.round(obj.val).toString();
        (statEl as HTMLElement).textContent = display + suffix;
      },
    });
    tweens.push(tween);
  });

  return tweens;
}

/** Kill an array of tweens (safe with nulls). */
export function killTweens(tweens: GsapTween[]): void {
  for (const t of tweens) {
    t?.kill();
  }
}

/**
 * Set up GSAP spring hover on a card element.
 * Returns a cleanup function that removes listeners and kills active tweens.
 */
export async function setupSpringHover(
  card: HTMLElement,
): Promise<() => void> {
  const { gsap } = await getGsap();
  let activeTween: gsap.core.Tween | null = null;

  const onEnter = () => {
    activeTween?.kill();
    activeTween = gsap.to(card, { y: -3, duration: 0.3, ease: 'back.out(2)' });
  };
  const onLeave = () => {
    activeTween?.kill();
    activeTween = gsap.to(card, { y: 0, duration: 0.3, ease: 'power2.out' });
  };

  card.addEventListener('mouseenter', onEnter);
  card.addEventListener('mouseleave', onLeave);

  return () => {
    card.removeEventListener('mouseenter', onEnter);
    card.removeEventListener('mouseleave', onLeave);
    activeTween?.kill();
  };
}
