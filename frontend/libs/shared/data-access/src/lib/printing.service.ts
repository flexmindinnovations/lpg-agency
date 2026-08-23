import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';

import { PrintJobRequest, PrintJobResponse } from './generated/models';

@Injectable({ providedIn: 'root' })
export class PrintingService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  /**
   * Request a print job from the backend. The backend renders the document
   * (PDF or thermal receipt) and returns a pre-signed download URL.
   */
  createPrintJob(request: PrintJobRequest): Observable<PrintJobResponse> {
    return this.http.post<PrintJobResponse>(
      `${this.config.rootUrl}/api/v1/print-jobs`,
      request,
    );
  }

  /**
   * Convenience method: render an invoice as PDF and open it in a new tab.
   */
  printInvoicePdf(invoiceId: string): Observable<PrintJobResponse> {
    return this.createPrintJob({
      document_type: 'invoice',
      document_id: invoiceId,
      format: 'pdf',
    }).pipe(
      tap((res) => {
        window.open(res.download_url, '_blank');
      }),
    );
  }

  /**
   * Convenience method: render an invoice as a thermal receipt (HTML page).
   * Unlike `printInvoicePdf`, this does NOT open the result itself — the
   * caller decides how to display it (e.g. embedded in a dialog via an
   * iframe, with a new-tab fallback), since a thermal receipt is small
   * enough to preview in-page without losing the caller's context.
   */
  printInvoiceThermal(invoiceId: string): Observable<PrintJobResponse> {
    return this.createPrintJob({
      document_type: 'invoice',
      document_id: invoiceId,
      format: 'thermal',
    });
  }
}
