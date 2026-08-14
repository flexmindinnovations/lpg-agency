import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  inject,
  signal,
  viewChild,
  DestroyRef,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { ButtonDirective } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { Textarea } from 'primeng/textarea';
import { MessageService } from 'primeng/api';
import {
  ComplaintService,
  type Complaint,
  type RaiseComplaintRequest,
  type AssignComplaintRequest,
  type ResolveComplaintRequest,
} from '../services/complaint.service';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';

function errorMessageFor(_error: unknown): string {
  // Add specific error handling if backend returns AppError structures
  return 'Something went wrong. Please try again.';
}

@Component({
  selector: 'lib-feature-complaints',
  imports: [
    DatePipe,
    // HeaderPortalDirective,
    // HeaderTitlePortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    // ButtonIcon,
    // ButtonLabel,
    Drawer,
    // IconField,
    // InputIcon,
    InputText,
    Select,
    Tag,
    Textarea,
    DataGridComponent,
  ],
  templateUrl: './feature-complaints.html',
  styleUrl: './feature-complaints.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [MessageService],
})
export class FeatureComplaints implements OnInit {
  private readonly complaintService = inject(ComplaintService);
  private readonly messageService = inject(MessageService);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly destroyRef = inject(DestroyRef);

  readonly registerTriggerEl = viewChild<ElementRef<HTMLButtonElement>>('registerTriggerEl');

  // State
  readonly complaints = signal<Complaint[]>([]);
  readonly loading = signal(true);

  // Drawer states
  readonly detailVisible = signal(false);
  readonly selectedComplaint = signal<Complaint | null>(null);

  readonly registerModalVisible = signal(false);
  readonly registerLoading = signal(false);

  readonly assignModalVisible = signal(false);
  readonly assignLoading = signal(false);

  readonly resolveModalVisible = signal(false);
  readonly resolveLoading = signal(false);

  // Grid config
  readonly columns: DataGridColumn<Complaint>[] = [
    {
      field: 'id',
      header: 'Complaint ID',
      width: 140,
      tooltipValueGetter: (val) => String(val),
      valueFormatter: (val) => String(val).substring(0, 8) + '...',
    },
    { field: 'category', header: 'Category', flex: 1, sortable: true },
    { field: 'priority', header: 'Priority', width: 150, sortable: true },
    { field: 'status', header: 'Status', width: 150, sortable: true },
    {
      field: 'customer_id',
      header: 'Customer ID',
      width: 150,
      tooltipValueGetter: (val) => String(val),
      valueFormatter: (val) => String(val).substring(0, 8) + '...',
    },
    {
      field: 'created_at',
      header: 'Raised On',
      width: 160,
      sortable: true,
      valueFormatter: (val) => new Date(String(val)).toLocaleDateString(),
    },
  ];

  // Forms
  readonly raiseForm = this.fb.group({
    customer_id: ['', Validators.required],
    category: ['', Validators.required],
    priority: ['Medium', Validators.required],
    description: ['', [Validators.required, Validators.minLength(10)]],
    order_id: [''],
  });

  readonly assignForm = this.fb.group({
    assigned_to: ['', Validators.required],
  });

  readonly resolveForm = this.fb.group({
    outcome: ['Resolved', Validators.required],
    resolution_notes: ['', [Validators.required, Validators.minLength(5)]],
  });

  readonly categoryOptions = [
    { label: 'Delivery Delay', value: 'Delivery Delay' },
    { label: 'Defective Cylinder', value: 'Defective Cylinder' },
    { label: 'Rude Behavior', value: 'Rude Behavior' },
    { label: 'Overcharging', value: 'Overcharging' },
    { label: 'Other', value: 'Other' },
  ];

  readonly priorityOptions = [
    { label: 'Critical', value: 'Critical' },
    { label: 'High', value: 'High' },
    { label: 'Medium', value: 'Medium' },
    { label: 'Low', value: 'Low' },
  ];

  readonly outcomeOptions = [
    { label: 'Resolved', value: 'Resolved' },
    { label: 'Compensated', value: 'Compensated' },
    { label: 'Rejected', value: 'Rejected' },
  ];

  ngOnInit() {
    this.loadComplaints();
  }

  loadComplaints() {
    this.loading.set(true);
    const sub = this.complaintService.listComplaints().subscribe({
      next: (res) => {
        this.complaints.set(res.items);
        this.loading.set(false);
      },
      error: (_err) => {
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: 'Failed to load complaints',
        });
        this.loading.set(false);
      },
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  onRowAction(complaint: Complaint) {
    this.selectedComplaint.set(complaint);
    this.detailVisible.set(true);
  }

  openRaiseModal() {
    this.raiseForm.reset({ priority: 'Medium' });
    this.registerModalVisible.set(true);
  }

  closeRaiseModal() {
    this.registerModalVisible.set(false);
    this.registerTriggerEl()?.nativeElement.focus();
  }

  submitRaise() {
    if (this.raiseForm.invalid) return;
    this.registerLoading.set(true);
    const val = this.raiseForm.getRawValue();

    const request: RaiseComplaintRequest = {
      customer_id: val.customer_id,
      category: val.category,
      priority: val.priority,
      description: val.description,
      order_id: val.order_id || undefined,
    };

    const sub = this.complaintService.raiseComplaint(request).subscribe({
      next: () => {
        this.messageService.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Complaint raised',
        });
        this.closeRaiseModal();
        this.loadComplaints();
        this.registerLoading.set(false);
      },
      error: (_err) => {
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: errorMessageFor(_err),
        });
        this.registerLoading.set(false);
      },
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  openAssignModal() {
    this.assignForm.reset();
    this.assignModalVisible.set(true);
  }

  closeAssignModal() {
    this.assignModalVisible.set(false);
  }

  submitAssign() {
    const complaint = this.selectedComplaint();
    if (this.assignForm.invalid || !complaint) return;

    this.assignLoading.set(true);
    const request: AssignComplaintRequest = {
      assigned_to: this.assignForm.getRawValue().assigned_to,
    };

    const sub = this.complaintService.assignComplaint(complaint.id, request).subscribe({
      next: () => {
        this.messageService.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Complaint assigned',
        });
        this.closeAssignModal();
        this.loadComplaints();
        // Refresh detail
        this.refreshDetail(complaint.id);
        this.assignLoading.set(false);
      },
      error: (_err) => {
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: errorMessageFor(_err),
        });
        this.assignLoading.set(false);
      },
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  openResolveModal() {
    this.resolveForm.reset({ outcome: 'Resolved' });
    this.resolveModalVisible.set(true);
  }

  closeResolveModal() {
    this.resolveModalVisible.set(false);
  }

  submitResolve() {
    const complaint = this.selectedComplaint();
    if (this.resolveForm.invalid || !complaint) return;

    this.resolveLoading.set(true);
    const val = this.resolveForm.getRawValue();
    const request: ResolveComplaintRequest = {
      outcome: val.outcome as 'Resolved' | 'Compensated' | 'Rejected',
      resolution_notes: val.resolution_notes,
    };

    const sub = this.complaintService.resolveComplaint(complaint.id, request).subscribe({
      next: () => {
        this.messageService.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Complaint resolved',
        });
        this.closeResolveModal();
        this.loadComplaints();
        // Refresh detail
        this.refreshDetail(complaint.id);
        this.resolveLoading.set(false);
      },
      error: (_err) => {
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: errorMessageFor(_err),
        });
        this.resolveLoading.set(false);
      },
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  private refreshDetail(id: string) {
    const sub = this.complaintService.getComplaint(id).subscribe({
      next: (comp) => {
        this.selectedComplaint.set(comp);
      },
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  getSeverity(status: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' | 'contrast' {
    switch (status) {
      case 'Resolved':
        return 'success';
      case 'Open':
        return 'warn';
      case 'InProgress':
        return 'info';
      case 'Closed':
        return 'secondary';
      case 'Rejected':
        return 'danger';
      default:
        return 'info';
    }
  }
}
