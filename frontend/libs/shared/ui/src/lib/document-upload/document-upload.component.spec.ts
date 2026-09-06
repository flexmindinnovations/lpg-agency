import { ComponentFixture, TestBed } from '@angular/core/testing';
import { type Observable, Subject, of, throwError } from 'rxjs';
import { DocumentUploadComponent, type DocumentUploadResult } from './document-upload.component';

type Uploader = (file: File) => Observable<DocumentUploadResult>;

function fileOf(name: string, type: string, size: number): File {
  return new File([new Blob(['x'.repeat(size)], { type })], name, { type });
}

describe('DocumentUploadComponent', () => {
  beforeEach(() => {
    // jsdom implements neither.
    URL.createObjectURL = jest.fn(() => 'blob:preview');
    URL.revokeObjectURL = jest.fn();
  });

  function render(uploader: Uploader): ComponentFixture<DocumentUploadComponent> {
    const fixture = TestBed.createComponent(DocumentUploadComponent);
    fixture.componentRef.setInput('uploader', uploader);
    fixture.detectChanges();
    return fixture;
  }

  function selectFile(fixture: ComponentFixture<DocumentUploadComponent>, file: File): void {
    const input = (fixture.nativeElement as HTMLElement).querySelector('input[type="file"]');
    if (!input) throw new Error('file input not rendered');
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change'));
    fixture.detectChanges();
  }

  it('shows the dropzone and hint until a file is chosen', () => {
    const fixture = render(() => of({ blobRef: 'ref' }));
    fixture.componentRef.setInput('hint', 'JPG or PNG · up to 10 MB');
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.lpg-doc-upload__dropzone')).not.toBeNull();
    expect(el.querySelector('.lpg-doc-upload__hint')?.textContent).toContain('up to 10 MB');
  });

  it('rejects a file over the size limit without calling the uploader', () => {
    const uploader = jest.fn(() => of({ blobRef: 'ref' }));
    const fixture = render(uploader);
    fixture.componentRef.setInput('maxBytes', 10);
    const errored = jest.fn();
    fixture.componentInstance.errored.subscribe(errored);

    selectFile(fixture, fileOf('big.png', 'image/png', 5000));

    expect(uploader).not.toHaveBeenCalled();
    expect(errored).toHaveBeenCalledWith(expect.stringContaining('too large'));
    expect((fixture.nativeElement as HTMLElement).querySelector('.lpg-doc-upload__error')).not.toBeNull();
  });

  it('rejects a disallowed file type', () => {
    const uploader = jest.fn(() => of({ blobRef: 'ref' }));
    const fixture = render(uploader);
    selectFile(fixture, fileOf('doc.pdf', 'application/pdf', 100));
    expect(uploader).not.toHaveBeenCalled();
  });

  it('uploads a valid file and emits `uploaded`', () => {
    const uploader = jest.fn(() => of({ blobRef: 'stored-ref' }));
    const fixture = render(uploader);
    const uploaded = jest.fn();
    fixture.componentInstance.uploaded.subscribe(uploaded);

    const file = fileOf('id.png', 'image/png', 200);
    selectFile(fixture, file);

    expect(uploader).toHaveBeenCalledWith(file);
    expect(uploaded).toHaveBeenCalledWith({ blobRef: 'stored-ref', file });
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.lpg-doc-upload__preview')).not.toBeNull();
    expect(el.querySelector('.lpg-doc-upload__status--ok')).not.toBeNull();
  });

  it('runs the recognizer after upload and emits `recognized`', () => {
    const fixture = render(() => of({ blobRef: 'r' }));
    fixture.componentRef.setInput('recognizer', () => of({ doc_type: 'aadhaar' }));
    const recognized = jest.fn();
    fixture.componentInstance.recognized.subscribe(recognized);

    selectFile(fixture, fileOf('id.png', 'image/png', 200));

    expect(recognized).toHaveBeenCalledWith({ doc_type: 'aadhaar' });
  });

  it('keeps the stored file when recognition fails', () => {
    const fixture = render(() => of({ blobRef: 'r' }));
    fixture.componentRef.setInput('recognizer', () => throwError(() => new Error('ocr down')));
    fixture.detectChanges();

    selectFile(fixture, fileOf('id.png', 'image/png', 200));

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.lpg-doc-upload__preview')).not.toBeNull();
    expect(el.querySelector('.lpg-doc-upload__error')?.textContent).toContain('by hand');
  });

  it('surfaces an upload failure', () => {
    const fixture = render(() => throwError(() => new Error('500')));
    selectFile(fixture, fileOf('id.png', 'image/png', 200));
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.lpg-doc-upload__status--err')).not.toBeNull();
  });

  it('clears back to the dropzone and emits `cleared`', () => {
    const upload$ = new Subject<DocumentUploadResult>();
    const fixture = render(() => upload$);
    const cleared = jest.fn();
    fixture.componentInstance.cleared.subscribe(cleared);

    selectFile(fixture, fileOf('id.png', 'image/png', 200));
    upload$.next({ blobRef: 'r' });
    upload$.complete();
    fixture.detectChanges();

    (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLButtonElement>('.lpg-doc-upload__remove')
      ?.click();
    fixture.detectChanges();

    expect(cleared).toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).querySelector('.lpg-doc-upload__dropzone')).not.toBeNull();
  });
});
