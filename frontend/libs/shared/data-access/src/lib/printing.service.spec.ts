import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ApiConfiguration } from './generated/api-configuration';
import { PrintingService } from './printing.service';
import { problemDetailsInterceptor, type AppError } from './problem-details';

describe('PrintingService', () => {
  let service: PrintingService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([problemDetailsInterceptor])),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'https://api.test' } },
      ],
    });
    service = TestBed.inject(PrintingService);
    http = TestBed.inject(HttpTestingController);
    expect(TestBed.inject(HttpClient)).toBeTruthy();
  });

  afterEach(() => http.verify());

  it('asks the server for the document itself, as a blob', () => {
    let received: Blob | undefined;
    service.renderInvoice('inv-1', 'pdf').subscribe((blob) => (received = blob));

    const req = http.expectOne('https://api.test/api/v1/print-jobs/document');
    expect(req.request.method).toBe('POST');
    expect(req.request.responseType).toBe('blob');
    expect(req.request.body).toEqual({
      document_type: 'invoice',
      document_id: 'inv-1',
      format: 'pdf',
    });
    req.flush(new Blob(['%PDF'], { type: 'application/pdf' }));

    expect(received?.type).toBe('application/pdf');
  });

  it('turns a JSON error sent as a blob into a typed error with the real message', async () => {
    const failure = new Promise<AppError>((resolve) =>
      service.renderInvoice('missing', 'thermal').subscribe({ error: resolve }),
    );

    const problem = {
      type: 'x',
      title: 'Not found',
      status: 404,
      error_code: 'RESOURCE_NOT_FOUND',
      detail: 'Invoice not found',
    };
    http
      .expectOne('https://api.test/api/v1/print-jobs/document')
      .flush(new Blob([JSON.stringify(problem)], { type: 'application/json' }), {
        status: 404,
        statusText: 'Not Found',
      });

    const error = await failure;
    expect(error.errorCode).toBe('RESOURCE_NOT_FOUND');
    expect(error.detail).toBe('Invoice not found');
  });

  it('shows the document in the pre-opened tab', () => {
    const create = jest.fn().mockReturnValue('blob:one');
    const revoke = jest.fn();
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke });
    const tab = { closed: false, location: { href: '' } } as unknown as Window;

    jest.useFakeTimers();
    service.showInTab(new Blob(['x']), tab, 'a.pdf');
    expect(tab.location.href).toBe('blob:one');
    expect(revoke).not.toHaveBeenCalled();
    jest.advanceTimersByTime(60_000);
    expect(revoke).toHaveBeenCalledWith('blob:one');
    jest.useRealTimers();
  });

  it('downloads the document when the tab was blocked', () => {
    Object.assign(URL, {
      createObjectURL: jest.fn().mockReturnValue('blob:two'),
      revokeObjectURL: jest.fn(),
    });
    const click = jest
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => undefined);

    service.showInTab(new Blob(['x']), null, 'a.pdf');

    expect(click).toHaveBeenCalled();
    click.mockRestore();
  });
});
