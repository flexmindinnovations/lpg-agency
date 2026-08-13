import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { of } from 'rxjs';
import { ApiConfiguration } from '@lpg/shared/data-access';
import { OrderQueue } from './order-queue';

describe('OrderQueue', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OrderQueue],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        {
          provide: ActivatedRoute,
          useValue: { queryParamMap: of(convertToParamMap({})) },
        },
      ],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(OrderQueue);
    const component = fixture.componentInstance;
    expect(component).toBeTruthy();
  });
});
