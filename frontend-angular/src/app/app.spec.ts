import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient()],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render title', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('AI Assistant');
  });

  it('should default to AUTO mode and contain the 3 tested demo suggestions', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app.mode).toBe('AUTO');
    expect(app.suggestions.length).toBe(3);
    expect(app.suggestions[0].prompt).toBe('What is the NovaMart return and refund policy?');
    expect(app.suggestions[1].prompt).toBe('What was the performance of campaign CMP-021?');
    expect(app.suggestions[2].prompt).toBe(
      'What were the results of campaign CMP-021 and what strategy was recommended?'
    );
  });

  it('should format markdown and sanitize HTML safely in formatMessage', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    const raw = '**Bold** and *italic*\n- Bullet item\n<script>alert(1)</script>';
    const safeHtml = app.formatMessage(raw);
    const htmlString = String(safeHtml);
    expect(htmlString).toContain('&lt;script&gt;');
    expect(htmlString).not.toContain('<script>');
  });
});

