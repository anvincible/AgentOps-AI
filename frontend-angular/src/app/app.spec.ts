import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { ComponentFixture } from '@angular/core/testing';
import { TestBed } from '@angular/core/testing';
import { App } from './app';

interface ClarificationContext {
  original_question: string;
  kind: string;
  options: string[];
  prompt: string;
}

describe('App', () => {
  let http: HttpTestingController;

  const productClarification: ClarificationContext = {
    original_question: 'Which product performed best?',
    kind: 'product_ranking_metric',
    options: ['revenue', 'quantity'],
    prompt: 'Should I rank products by quantity sold or by revenue?',
  };

  const customerClarification: ClarificationContext = {
    original_question: 'Show customer distribution.',
    kind: 'customer_distribution_dimension',
    options: ['segment', 'location', 'city', 'state', 'country', 'loyalty tier', 'acquisition channel'],
    prompt: 'Which supported dimension should I use: segment, location, loyalty tier, or acquisition channel?',
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function createApp() {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    http.expectOne('/api/health').flush({ status: 'ok' });
    fixture.detectChanges();
    return { fixture, app: fixture.componentInstance };
  }

  function requestClarification(
    fixture: ComponentFixture<App>,
    app: App,
    question: string,
    clarification: ClarificationContext,
  ): void {
    app.question = question;
    app.sendQuestion();
    const request = http.expectOne('/api/ask');
    expect(request.request.body).toEqual({ question });
    request.flush({
      question,
      route: 'CLARIFY',
      answer: clarification.prompt,
      sources: [],
      verification: { verified: true, route: 'CLARIFY' },
      clarification,
    });
    fixture.detectChanges();
  }

  it('creates and renders the assistant', () => {
    const { fixture, app } = createApp();
    expect(app).toBeTruthy();
    expect((fixture.nativeElement as HTMLElement).querySelector('h1')?.textContent)
      .toContain('AI Assistant');
  });

  it('keeps the three existing demo suggestions', () => {
    const { app } = createApp();
    expect(app.suggestions.length).toBe(3);
    expect(app.suggestions[0].prompt).toBe('What is the NovaMart return and refund policy?');
    expect(app.suggestions[1].prompt).toBe('What was the performance of campaign CMP-021?');
    expect(app.suggestions[2].prompt).toBe(
      'What were the results of campaign CMP-021 and what strategy was recommended?',
    );
  });

  it('shows clarification prompt and options without a misleading verified-answer card', () => {
    const { fixture, app } = createApp();
    requestClarification(
      fixture,
      app,
      productClarification.original_question,
      productClarification,
    );

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.clarification-prompt')?.textContent)
      .toContain(productClarification.prompt);
    expect(element.querySelectorAll('.clarification-option').length).toBe(2);
    expect(element.querySelector('.verification-card')).toBeNull();
  });

  it('sends the exact backend clarification context when an option is selected', () => {
    const { fixture, app } = createApp();
    requestClarification(
      fixture,
      app,
      productClarification.original_question,
      productClarification,
    );

    const button = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>(
        '.clarification-option',
      ),
    ).find((option) => option.textContent?.includes('Revenue'));
    expect(button).toBeTruthy();
    button!.click();
    fixture.detectChanges();

    const request = http.expectOne('/api/ask');
    expect(request.request.body).toEqual({
      question: 'By revenue',
      clarification_context: productClarification,
    });
    request.flush({
      route: 'SQL',
      answer: 'GreenBasket Audio Series 0057 ranked first by revenue.',
      sources: [{ type: 'sql', title: 'NovaMart PostgreSQL database' }],
      verification: { verified: true, route: 'SQL' },
      clarification: null,
    });
    fixture.detectChanges();

    expect(app.pendingClarification).toBeNull();
    expect(app.messages.map((message) => message.role)).toEqual([
      'user', 'assistant', 'user', 'assistant',
    ]);
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.clarification-option'),
    ).toBeNull();
  });

  it('sends typed clarification text with the backend context and clears it after resolution', () => {
    const { fixture, app } = createApp();
    requestClarification(
      fixture,
      app,
      productClarification.original_question,
      productClarification,
    );

    app.question = 'By revenue';
    app.sendQuestion();
    const request = http.expectOne('/api/ask');
    expect(request.request.body).toEqual({
      question: 'By revenue',
      clarification_context: productClarification,
    });
    request.flush({ route: 'SQL', answer: 'A verified product ranking.', clarification: null });
    fixture.detectChanges();
    expect(app.pendingClarification).toBeNull();
  });

  it('does not send stale clarification context with an unrelated question', () => {
    const { fixture, app } = createApp();
    requestClarification(
      fixture,
      app,
      productClarification.original_question,
      productClarification,
    );

    app.question = 'How many customers are in the database?';
    app.sendQuestion();
    const request = http.expectOne('/api/ask');
    expect(request.request.body).toEqual({
      question: 'How many customers are in the database?',
    });
    expect(app.pendingClarification).toBeNull();
    request.flush({ route: 'SQL', answer: '10,000 customers.', clarification: null });
    fixture.detectChanges();
  });

  it('clears pending context and messages when starting a new chat', () => {
    const { fixture, app } = createApp();
    requestClarification(
      fixture,
      app,
      customerClarification.original_question,
      customerClarification,
    );
    expect(app.pendingClarification).toEqual(customerClarification);

    app.newChat();
    expect(app.pendingClarification).toBeNull();
    expect(app.messages).toEqual([]);
  });

  it('keeps one-shot requests compatible and continues rendering citations and verification', () => {
    const { fixture, app } = createApp();
    app.question = 'What is the NovaMart return and refund policy?';
    app.sendQuestion();
    const request = http.expectOne('/api/ask');
    expect(request.request.body).toEqual({
      question: 'What is the NovaMart return and refund policy?',
    });
    request.flush({
      route: 'RAG',
      answer: 'Eligible returns may be requested within 30 days.',
      sources: [{ type: 'document', document_id: 'DOC-POL-001', title: 'Return Refund Policy' }],
      verification: { verified: true, route: 'RAG', checks: ['Evidence supports the answer.'] },
    });
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.source-card')?.textContent).toContain('DOC-POL-001');
    expect(element.querySelector('.verification-card')?.textContent)
      .toContain('Basic checks passed');
    expect(app.pendingClarification).toBeNull();
  });

  it('shows server errors once without duplicating them in the error banner', () => {
    const { fixture, app } = createApp();
    app.question = 'A question that fails';
    app.sendQuestion();
    http.expectOne('/api/ask').flush(
      { detail: 'The API request failed.' },
      { status: 500, statusText: 'Server Error' },
    );
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.assistant-message .answer-text')?.textContent)
      .toContain('The API request failed.');
    expect(element.querySelector('.error-banner')).toBeNull();
    expect(element.textContent?.match(/The API request failed\./g)?.length).toBe(1);
  });

  it('formats markdown and escapes HTML safely', () => {
    const { app } = createApp();
    const raw = '**Bold** and *italic*\n- Bullet item\n<script>alert(1)</script>';
    const html = String(app.formatMessage(raw));
    expect(html).toContain('&lt;script&gt;');
    expect(html).not.toContain('<script>');
  });
});
