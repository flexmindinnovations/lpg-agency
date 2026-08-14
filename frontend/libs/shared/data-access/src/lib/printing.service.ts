import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';

export interface PrintJobRequest {
  document_type: string;
  document_id: string;
  format: 'pdf' | 'thermal';
}

export interface PrintJobResponse {
  download_url: string;
  format: string;
  content_type: string;
}

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
   * Convenience method: render an invoice as a thermal receipt text file.
   */
  printInvoiceThermal(invoiceId: string): Observable<PrintJobResponse> {
    return this.createPrintJob({
      document_type: 'invoice',
      document_id: invoiceId,
      format: 'thermal',
    }).pipe(
      tap((res) => {
        window.open(res.download_url, '_blank');
      }),
    );
  }
}
