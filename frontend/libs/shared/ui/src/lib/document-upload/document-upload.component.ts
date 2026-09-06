import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import type { Observable } from 'rxjs';

/** What a call site's upload function must resolve to. */
export interface DocumentUploadResult {
  blobRef: string;
}

/** Emitted once the file is stored server-side. */
export interface DocumentUploaded {
  blobRef: string;
  file: File;
}

type Stage = 'idle' | 'uploading' | 'analyzing' | 'done' | 'error';

const DEFAULT_MAX_BYTES = 10 * 1024 * 1024;

/**
 * The standard "upload a document image/scan" control — dropzone, drag & drop,
 * type/size guard, thumbnail (image) or icon (PDF) preview, and an
 * upload → optional server-side recognition status line.
 *
 * Deliberately endpoint-agnostic: the call site passes an `uploader` (and an
 * optional `recognizer`) function and reacts to the `uploaded` / `recognized`
 * outputs. The component owns none of the form-fill logic — mapping a
 * recognition result onto a reactive form stays with the parent, which is the
 * only thing that knows the shape of that form.
 *
 * ```html
 * <lpg-document-upload
 *   accept="image/*"
 *   hint="Aadhaar or PAN card · JPG or PNG · up to 10 MB"
 *   [uploader]="uploadFn"
 *   [recognizer]="recognizeFn"
 *   (uploaded)="onUploaded($event)"
 *   (recognized)="applyExtracted($event)"
 * />
 * ```
 */
@Component({
  selector: 'lpg-document-upload',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (!fileName()) {
      <div
        class="lpg-doc-upload__dropzone"
        [class.lpg-doc-upload__dropzone--dragging]="isDragging()"
        [class.lpg-doc-upload__dropzone--disabled]="disabled()"
        (dragover)="onDragOver($event)"
        (dragleave)="onDragLeave($event)"
        (drop)="onDrop($event)"
      >
        <i class="pi pi-cloud-upload lpg-doc-upload__icon" aria-hidden="true"></i>
        <p class="lpg-doc-upload__title">Drag &amp; drop your document here</p>
        <p class="lpg-doc-upload__or">or</p>
        <input
          #fileInput
          class="lpg-doc-upload__input"
          type="file"
          [attr.id]="inputId()"
          [accept]="accept()"
          [disabled]="disabled()"
          (change)="onFileSelected($event)"
        />
        <label [attr.for]="inputId()" class="lpg-doc-upload__browse">
          <i class="pi pi-folder-open" aria-hidden="true"></i>
          Browse files
        </label>
        @if (hint()) {
          <p class="lpg-doc-upload__hint">{{ hint() }}</p>
        }
      </div>
    } @else {
      <div class="lpg-doc-upload__preview">
        @if (previewUrl()) {
          <img [src]="previewUrl()" class="lpg-doc-upload__thumb" alt="Document preview" />
        } @else {
          <div class="lpg-doc-upload__thumb lpg-doc-upload__thumb--icon">
            <i class="pi pi-file" aria-hidden="true"></i>
          </div>
        }
        <div class="lpg-doc-upload__info">
          <span class="lpg-doc-upload__name">{{ fileName() }}</span>
          @if (fileSize(); as size) {
            <span class="lpg-doc-upload__size">{{ formatSize(size) }}</span>
          }
          @switch (stage()) {
            @case ('uploading') {
              <span class="lpg-doc-upload__status">
                <i class="pi pi-spin pi-spinner" aria-hidden="true"></i> Uploading…
              </span>
            }
            @case ('analyzing') {
              <span class="lpg-doc-upload__status">
                <i class="pi pi-spin pi-spinner" aria-hidden="true"></i> Reading document…
              </span>
            }
            @case ('done') {
              <span class="lpg-doc-upload__status lpg-doc-upload__status--ok">
                <i class="pi pi-check-circle" aria-hidden="true"></i> Uploaded
              </span>
            }
            @case ('error') {
              <span class="lpg-doc-upload__status lpg-doc-upload__status--err">
                <i class="pi pi-exclamation-triangle" aria-hidden="true"></i> Failed
              </span>
            }
          }
        </div>
        <button
          type="button"
          class="lpg-doc-upload__remove"
          [disabled]="disabled() || stage() === 'uploading'"
          (click)="clear()"
          aria-label="Remove file"
        >
          <i class="pi pi-times" aria-hidden="true"></i>
        </button>
      </div>
    }

    @if (errorMessage(); as msg) {
      <p class="lpg-doc-upload__error" role="alert">
        <i class="pi pi-exclamation-triangle" aria-hidden="true"></i> {{ msg }}
      </p>
    }
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .lpg-doc-upload__dropzone {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--spacing-xs);
        border: 2px dashed var(--color-border-default);
        border-radius: var(--radius-lg);
        padding: var(--spacing-xl) var(--spacing-lg);
        text-align: center;
        color: var(--color-text-secondary);
        background: var(--color-surface-base);
        transition:
          border-color var(--motion-duration-small) var(--motion-easing-standard),
          background-color var(--motion-duration-small) var(--motion-easing-standard);
      }

      .lpg-doc-upload__dropzone--dragging {
        border-color: var(--color-action-primary);
        background: var(--color-highlight-background);
      }

      .lpg-doc-upload__dropzone--disabled {
        opacity: 0.6;
        pointer-events: none;
      }

      .lpg-doc-upload__icon {
        font-size: 2.5rem;
        color: var(--color-action-primary);
        margin-block-end: var(--spacing-xs);
      }

      .lpg-doc-upload__title {
        margin: 0;
        font-size: var(--typography-body-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-primary);
      }

      .lpg-doc-upload__or {
        margin: 0;
        font-size: var(--typography-caption-font-size);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      .lpg-doc-upload__input {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }

      .lpg-doc-upload__browse {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        padding: var(--spacing-sm) var(--spacing-lg);
        border: var(--border-width) solid var(--color-action-primary);
        border-radius: var(--radius-md);
        background: var(--color-surface-base);
        color: var(--color-action-primary);
        font-size: var(--typography-body-small-font-size);
        font-weight: var(--typography-label-font-weight);
        cursor: pointer;
        transition:
          background-color var(--motion-duration-small) var(--motion-easing-standard),
          color var(--motion-duration-small) var(--motion-easing-standard);
      }

      .lpg-doc-upload__browse:hover {
        background: var(--color-action-primary);
        color: var(--color-action-primary-text);
      }

      .lpg-doc-upload__input:focus-visible + .lpg-doc-upload__browse {
        outline: 2px solid var(--color-border-focus);
        outline-offset: 2px;
      }

      .lpg-doc-upload__hint {
        margin: var(--spacing-xs) 0 0;
        font-size: var(--typography-caption-font-size);
      }

      .lpg-doc-upload__preview {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-lg);
        padding: var(--spacing-sm);
        background: var(--color-surface-base);
      }

      .lpg-doc-upload__thumb {
        inline-size: 64px;
        block-size: 64px;
        flex-shrink: 0;
        object-fit: cover;
        border-radius: var(--radius-md);
        border: var(--border-width) solid var(--color-border-default);
      }

      .lpg-doc-upload__thumb--icon {
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        color: var(--color-text-secondary);
        background: var(--color-surface-raised);
      }

      .lpg-doc-upload__info {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
        flex: 1;
        min-inline-size: 0;
      }

      .lpg-doc-upload__name {
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-primary);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .lpg-doc-upload__size {
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }

      .lpg-doc-upload__status {
        display: flex;
        align-items: center;
        gap: var(--spacing-xs);
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }

      .lpg-doc-upload__status--ok {
        color: var(--color-status-success);
      }

      .lpg-doc-upload__status--err {
        color: var(--color-status-danger);
      }

      .lpg-doc-upload__remove {
        display: flex;
        align-items: center;
        justify-content: center;
        inline-size: 32px;
        block-size: 32px;
        flex-shrink: 0;
        border: none;
        border-radius: 50%;
        background: transparent;
        color: var(--color-text-secondary);
        cursor: pointer;
        transition:
          background-color var(--motion-duration-small) var(--motion-easing-standard),
          color var(--motion-duration-small) var(--motion-easing-standard);
      }

      .lpg-doc-upload__remove:hover:not(:disabled) {
        background: var(--color-surface-raised);
        color: var(--color-status-danger);
      }

      .lpg-doc-upload__remove:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .lpg-doc-upload__error {
        display: flex;
        align-items: center;
        gap: var(--spacing-xs);
        margin: var(--spacing-xs) 0 0;
        font-size: var(--typography-body-small-font-size);
        color: var(--color-status-danger);
      }
    `,
  ],
})
export class DocumentUploadComponent {
  private readonly destroyRef = inject(DestroyRef);

  /** `accept` attribute for the file input. */
  readonly accept = input('image/*');
  /** Reject files larger than this (bytes). */
  readonly maxBytes = input(DEFAULT_MAX_BYTES);
  /** Small print under the dropzone. */
  readonly hint = input('');
  readonly disabled = input(false);
  /** `id` for the hidden input so an external `<label for>` can target it. */
  readonly inputId = input('lpg-doc-upload-input');

  /** Stores the file server-side; must resolve to `{ blobRef }`. Required. */
  readonly uploader = input.required<(file: File) => Observable<DocumentUploadResult>>();
  /** Optional server-side recognition pass, keyed by the stored blob ref. */
  readonly recognizer = input<((blobRef: string) => Observable<unknown>) | null>(null);

  readonly uploaded = output<DocumentUploaded>();
  readonly recognized = output<unknown>();
  readonly cleared = output<void>();
  readonly errored = output<string>();

  protected readonly stage = signal<Stage>('idle');
  protected readonly fileName = signal<string | null>(null);
  protected readonly fileSize = signal<number | null>(null);
  protected readonly previewUrl = signal<string | null>(null);
  protected readonly isDragging = signal(false);
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly isImage = computed(() => this.accept().includes('image'));

  constructor() {
    this.destroyRef.onDestroy(() => this.revokePreview());
  }

  protected onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (file) this.process(file);
  }

  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
    if (!this.disabled()) this.isDragging.set(true);
  }

  protected onDragLeave(event: DragEvent): void {
    event.preventDefault();
    this.isDragging.set(false);
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragging.set(false);
    if (this.disabled()) return;
    const file = event.dataTransfer?.files?.[0];
    if (file) this.process(file);
  }

  protected clear(): void {
    this.revokePreview();
    this.fileName.set(null);
    this.fileSize.set(null);
    this.previewUrl.set(null);
    this.errorMessage.set(null);
    this.stage.set('idle');
    this.cleared.emit();
  }

  protected formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  private process(file: File): void {
    const accepted = this.accept()
      .split(',')
      .map((t) => t.trim());
    const typeOk = accepted.some((t) =>
      t.endsWith('/*') ? file.type.startsWith(t.slice(0, -1)) : file.type === t,
    );
    if (!typeOk) {
      this.fail('Unsupported file type.');
      return;
    }
    if (file.size > this.maxBytes()) {
      this.fail(`File is too large. Maximum ${this.formatSize(this.maxBytes())}.`);
      return;
    }

    this.errorMessage.set(null);
    this.fileName.set(file.name);
    this.fileSize.set(file.size);
    this.revokePreview();
    this.previewUrl.set(
      file.type.startsWith('image/') ? URL.createObjectURL(file) : null,
    );
    this.stage.set('uploading');

    this.uploader()(file)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          // Guard against a result landing after the user cleared the field.
          if (!this.fileName()) return;
          this.uploaded.emit({ blobRef: res.blobRef, file });
          const recognizer = this.recognizer();
          if (recognizer) {
            this.runRecognizer(recognizer, res.blobRef);
          } else {
            this.stage.set('done');
          }
        },
        error: () => this.fail('Could not upload the document. Please try again.'),
      });
  }

  private runRecognizer(
    recognizer: (blobRef: string) => Observable<unknown>,
    blobRef: string,
  ): void {
    this.stage.set('analyzing');
    recognizer(blobRef)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          if (!this.fileName()) return;
          this.stage.set('done');
          this.recognized.emit(result);
        },
        // A failed read is not a failed upload — the file is stored, the user
        // can still fill fields by hand.
        error: () => {
          this.stage.set('done');
          this.errorMessage.set(
            'Could not read the document automatically. Please enter the details by hand.',
          );
        },
      });
  }

  private fail(message: string): void {
    this.stage.set('error');
    this.errorMessage.set(message);
    this.errored.emit(message);
  }

  private revokePreview(): void {
    const url = this.previewUrl();
    if (url) URL.revokeObjectURL(url);
  }
}
