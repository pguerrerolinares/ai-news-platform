import { Page } from '@playwright/test';

/**
 * Completa todas las animaciones en curso y desactiva futuras animaciones/transiciones.
 *
 * Usa la Web Animations API para saltar cada animacion finita a su estado final
 * (opacity: 1, transform: none, etc.) y cancela las infinitas (shimmer, blink, pulse).
 */
export async function freezeAnimations(page: Page): Promise<void> {
  await page.evaluate(() => {
    for (const anim of document.getAnimations()) {
      const effect = anim.effect as KeyframeEffect | null;
      const timing = effect?.getComputedTiming();
      // Infinite animations have Infinity duration — cancel them
      if (timing && timing.endTime === Infinity) {
        anim.cancel();
      } else {
        anim.finish();
      }
    }
  });
  // Disable any future animations/transitions
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
      }
    `,
  });
}
