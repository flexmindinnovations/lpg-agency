import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { ApiConfiguration } from '@lpg/shared/data-access';
import { AgencyManagementPage } from './agency-management-page';

describe('AgencyManagementPage', () => {
  let component: AgencyManagementPage;
  let fixture: ComponentFixture<AgencyManagementPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AgencyManagementPage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        MessageService,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(AgencyManagementPage);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
