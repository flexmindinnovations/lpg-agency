import { TestBed } from '@angular/core/testing';
import { MessageService } from 'primeng/api';
import { NotifyService } from './notify.service';

describe('NotifyService', () => {
  let service: NotifyService;
  let messageService: MessageService;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [MessageService] });
    service = TestBed.inject(NotifyService);
    messageService = TestBed.inject(MessageService);
    jest.spyOn(messageService, 'add');
  });

  it('success() adds a success-severity toast with a default summary', () => {
    service.success('Saved.');
    expect(messageService.add).toHaveBeenCalledWith({
      severity: 'success',
      summary: 'Success',
      detail: 'Saved.',
      life: 4000,
    });
  });

  it('info() adds an info-severity toast', () => {
    service.info('Heads up.');
    expect(messageService.add).toHaveBeenCalledWith({
      severity: 'info',
      summary: 'Info',
      detail: 'Heads up.',
      life: 4000,
    });
  });

  it('warn() adds a warn-severity toast', () => {
    service.warn('Careful.');
    expect(messageService.add).toHaveBeenCalledWith({
      severity: 'warn',
      summary: 'Warning',
      detail: 'Careful.',
      life: 5000,
    });
  });

  it('error() adds an error-severity toast', () => {
    service.error('Failed.');
    expect(messageService.add).toHaveBeenCalledWith({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed.',
      life: 6000,
    });
  });

  it('accepts a custom summary', () => {
    service.success('Saved.', 'Branch created');
    expect(messageService.add).toHaveBeenCalledWith(
      expect.objectContaining({ summary: 'Branch created' }),
    );
  });
});
