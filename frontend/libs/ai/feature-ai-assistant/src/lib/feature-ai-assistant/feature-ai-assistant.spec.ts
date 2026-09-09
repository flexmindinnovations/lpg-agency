import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { FeatureAiAssistant } from './feature-ai-assistant';
import { ApiConfiguration } from '@lpg/shared/data-access';

describe('FeatureAiAssistant', () => {
  let component: FeatureAiAssistant;
  let fixture: ComponentFixture<FeatureAiAssistant>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureAiAssistant],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureAiAssistant);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);

    // The empty-state KPI snapshot fetches this once, from the
    // constructor — flush it here so every test starts from a clean
    // request queue, matching DashboardService.getSummary()'s real shape.
    httpMock.expectOne('http://test/api/v1/dashboard/summary').flush({
      customer_count: 0,
      driver_count: 0,
      vehicle_count: 0,
      vehicles_by_status: {},
      warehouse_count: 0,
      cylinder_type_count: 0,
      inventory_by_status: {},
      price_cards: [],
      recent_activity: [],
    });
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('does nothing when asked with an empty question', () => {
    component['question'].set('   ');
    component['ask']();
    httpMock.expectNone('http://test/api/v1/ai/ask');
  });

  it('posts the question and records the answer in history', () => {
    component['question'].set("What's today's inventory?");
    component['ask']();

    const req = httpMock.expectOne('http://test/api/v1/ai/ask');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ question: "What's today's inventory?" });
    req.flush({
      answer: 'You have 1200 filled cylinders.',
      tools_used: ['get_inventory_overview'],
      disabled_reason: null,
    });

    expect(component['history']()).toHaveLength(1);
    expect(component['history']()[0].response?.answer).toBe('You have 1200 filled cylinders.');
    expect(component['question']()).toBe('');
  });

  it('renders a disabled_reason as a non-error history entry', () => {
    component['question'].set('Anything?');
    component['ask']();

    const req = httpMock.expectOne('http://test/api/v1/ai/ask');
    req.flush({ answer: null, tools_used: [], disabled_reason: 'gateway_disabled' });

    const entry = component['history']()[0];
    expect(entry.error).toBe(false);
    expect(entry.response?.disabled_reason).toBe('gateway_disabled');
  });
});
