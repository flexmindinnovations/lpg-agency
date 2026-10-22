import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { PageHeaderComponent } from '@lpg/shared/ui';

@Component({
  selector: 'lib-reports-layout',
  standalone: true,
  imports: [CommonModule, RouterModule, HeaderTitlePortalDirective, PageHeaderComponent],
  templateUrl: './reports-layout.html',
  styleUrl: './reports-layout.css',
})
export class ReportsLayout {}
