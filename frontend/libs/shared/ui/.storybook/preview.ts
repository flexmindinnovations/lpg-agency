import type { Preview } from '@storybook/angular';
import { applicationConfig } from '@storybook/angular';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { providePrimeNG } from 'primeng/config';
import { LpgPrimeNgPreset } from '@lpg/shared/design-tokens';

import '../../../../libs/shared/design-tokens/src/lib/tokens.css';
import 'primeicons/primeicons.css';

/**
 * Storybook preview — every component renders through the same token
 * cascade and PrimeNG preset the real app uses (never a Storybook-only
 * stylesheet), so a story is honest evidence of how the component actually
 * looks, not a lookalike.
 */
const preview: Preview = {
  decorators: [
    applicationConfig({
      providers: [
        provideAnimationsAsync(),
        providePrimeNG({
          theme: { preset: LpgPrimeNgPreset, options: { darkModeSelector: '[data-theme="dark"]' } },
        }),
      ],
    }),
  ],
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
};

export default preview;
