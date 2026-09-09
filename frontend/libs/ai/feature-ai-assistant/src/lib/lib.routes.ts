import { Route } from '@angular/router';

export const aiFeatureAiAssistantRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./feature-ai-assistant/feature-ai-assistant').then((m) => m.FeatureAiAssistant),
  },
];
