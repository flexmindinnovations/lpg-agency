import type { Meta, StoryObj } from '@storybook/angular';
import { applicationConfig, moduleMetadata } from '@storybook/angular';
import { Component } from '@angular/core';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { type Observable, delay, of } from 'rxjs';
import { DocumentUploadComponent, type DocumentUploadResult } from './document-upload.component';

@Component({
  selector: 'lpg-document-upload-story-host',
  standalone: true,
  imports: [DocumentUploadComponent],
  template: `
    <div style="max-inline-size: 460px; display: flex; flex-direction: column; gap: 28px;">
      <div>
        <p style="font: 500 13px system-ui; margin: 0 0 8px;">Upload only</p>
        <lpg-document-upload
          hint="Aadhaar or PAN card · JPG or PNG · up to 10 MB"
          [uploader]="uploader"
        />
      </div>

      <div>
        <p style="font: 500 13px system-ui; margin: 0 0 8px;">Upload + server-side recognition</p>
        <lpg-document-upload
          accept="image/*,application/pdf"
          hint="Driving licence · image or PDF"
          [uploader]="uploader"
          [recognizer]="recognizer"
        />
      </div>
    </div>
  `,
})
class DocumentUploadStoryHost {
  uploader = (): Observable<DocumentUploadResult> =>
    of({ blobRef: 'demo/blob-ref' }).pipe(delay(700));
  recognizer = (): Observable<unknown> =>
    of({ document_number: 'MH12 20200012345' }).pipe(delay(900));
}

const meta: Meta<DocumentUploadStoryHost> = {
  title: 'Shared UI/Document Upload',
  component: DocumentUploadStoryHost,
  decorators: [
    applicationConfig({ providers: [provideAnimationsAsync()] }),
    moduleMetadata({ imports: [DocumentUploadComponent] }),
  ],
};
export default meta;
type Story = StoryObj<DocumentUploadStoryHost>;

export const States: Story = {};
