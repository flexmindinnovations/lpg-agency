import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';

@Component({
  selector: 'lib-reports-layout',
  standalone: true,
  imports: [CommonModule, RouterModule, HeaderTitlePortalDirective],
  templateUrl: './reports-layout.html',
  styleUrl: './reports-layout.css',
})
export class ReportsLayout {}
