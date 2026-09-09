import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { askAiAssistantApiV1AiAskPost } from './generated/fn/ai/ask-ai-assistant-api-v-1-ai-ask-post';
import type { AskAiAssistantResponse } from './generated/models/ask-ai-assistant-response';

/**
 * Thin wrapper over the generated `/ai/ask` client function — same pattern
 * as every other `shared/data-access` service. Feeds the AI Command Center
 * page (ADR-045).
 */
@Injectable({ providedIn: 'root' })
export class AiAssistantService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  ask(question: string): Observable<AskAiAssistantResponse> {
    return askAiAssistantApiV1AiAskPost(this.http, this.config.rootUrl, {
      body: { question },
    }).pipe(map((res) => res.body));
  }
}
