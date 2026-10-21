import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';

import { PrintJobRequest } from './generated/models';

export type PrintFormat = 'pdf' | 'thermal';

@Injectable({ providedIn: 'root' })
export class PrintingService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  /**
   * Render a document on the server and receive it directly (no file storage
   * involved). The request goes through the normal interceptors, so the auth
   * and tenant headers apply.
   */
  renderDocument(request: PrintJobRequest): Observable<Blob> {
    return this.http.post(`${this.config.rootUrl}/api/v1/print-jobs/document`, request, {
      responseType: 'blob',
    });
  }

  /** Render an invoice as a PDF or as a thermal receipt (HTML page). */
  renderInvoice(invoiceId: string, format: PrintFormat): Observable<Blob> {
    return this.renderDocument({
      document_type: 'invoice',
      document_id: invoiceId,
      format,
    });
  }

  /**
   * Open a blank tab right now, from inside the click handler. Browsers only
   * allow a pop-up that is opened synchronously by a user action; opening it
   * after the network call (as before) was often blocked.
   */
  openPendingTab(): Window | null {
    return window.open('', '_blank');
  }

  /**
   * Show a rendered document in the tab from `openPendingTab()`, or download
   * it when the tab was blocked. The blob URL is released after a minute, long
   * enough for the viewer to have loaded it.
   */
  showInTab(blob: Blob, tab: Window | null, filename: string): void {
    const url = URL.createObjectURL(blob);
    if (tab && !tab.closed) {
      tab.location.href = url;
    } else {
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      link.click();
    }
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }
}
