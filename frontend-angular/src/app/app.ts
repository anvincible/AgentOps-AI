
import { CommonModule } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectorRef,
  Component,
  OnInit,
  inject,
} from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';
import { TimeoutError, finalize, timeout } from 'rxjs';

interface SourceDocument {
  type?: string;
  title?: string;
  document_id?: string;
  filename?: string;
  document_type?: string;
  page_number?: number | null;
  paragraph_number?: number | null;
  chunk_id?: string;
}

interface VerificationResult {
  verified?: boolean;
  route?: string;
  checks?: string[];
  issues?: string[];
}

interface AskResponse {
  question?: string;
  route?: string;
  answer?: string;
  sources?: SourceDocument[];
  verification?: VerificationResult;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  route?: string;
  sources?: SourceDocument[];
  verification?: VerificationResult;
  pending?: boolean;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly sanitizer = inject(DomSanitizer);

  question = '';
  loading = false;
  backendOnline: boolean | null = null;
  activePage = 'assistant';
  errorMessage = '';
  messages: ChatMessage[] = [];

  readonly suggestions = [
    {
      icon: 'pi pi-file-check',
      title: 'Return and refund policy',
      prompt: 'What is the NovaMart return and refund policy?',
      description: 'Find policy details in company documents',
    },
    {
      icon: 'pi pi-chart-bar',
      title: 'Campaign performance',
      prompt: 'What was the performance of campaign CMP-021?',
      description: 'Explore structured business metrics',
    },
    {
      icon: 'pi pi-share-alt',
      title: 'Campaign results & strategy',
      prompt: 'What were the results of campaign CMP-021 and what strategy was recommended?',
      description: 'Combine structured metrics with strategy documents',
    },
  ];

  ngOnInit(): void {
    this.checkBackend();
  }

  checkBackend(): void {
    this.http
      .get<{ status?: string }>('/api/health')
      .pipe(timeout(5000))
      .subscribe({
        next: () => {
          this.backendOnline = true;
          this.changeDetector.detectChanges();
        },
        error: () => {
          this.backendOnline = false;
          this.changeDetector.detectChanges();
        },
      });
  }

  selectSuggestion(suggestion: { prompt: string }): void {
    this.question = suggestion.prompt;
    this.sendQuestion();
  }

  onEnter(event: Event): void {
    const keyboardEvent = event as KeyboardEvent;

    if (!keyboardEvent.shiftKey) {
      keyboardEvent.preventDefault();
      this.sendQuestion();
    }
  }

  sendQuestion(): void {
    const question = this.question.trim();

    if (!question || this.loading) {
      return;
    }

    this.errorMessage = '';
    this.loading = true;
    this.question = '';

    this.messages.push({
      role: 'user',
      content: question,
    });

    const assistantMessage: ChatMessage = {
      role: 'assistant',
      content: '',
      pending: true,
    };

    this.messages.push(assistantMessage);

    this.http
      .post<AskResponse>('/api/ask', { question })
      .pipe(
        timeout(60000),
        finalize(() => {
          assistantMessage.pending = false;
          this.loading = false;
          this.messages = [...this.messages];
          this.changeDetector.detectChanges();
        }),
      )
      .subscribe({
        next: (response) => {
          assistantMessage.content =
            typeof response?.answer === 'string' &&
            response.answer.trim().length > 0
              ? response.answer
              : 'The API responded, but no answer was returned.';

          assistantMessage.route = response?.route;
          assistantMessage.sources = Array.isArray(response?.sources)
            ? response.sources
            : [];
          assistantMessage.verification = response?.verification;
          assistantMessage.pending = false;
          this.backendOnline = true;
          this.messages = [...this.messages];
          this.changeDetector.detectChanges();
        },

        error: (error: unknown) => {
          assistantMessage.content = this.getErrorMessage(error);
          assistantMessage.sources = [];
          assistantMessage.verification = undefined;
          assistantMessage.pending = false;

          if (error instanceof HttpErrorResponse && error.status === 0) {
            this.backendOnline = false;
            this.errorMessage =
              'Cannot reach the backend. Check that FastAPI and the Angular proxy are running.';
          } else {
            this.backendOnline = true;
            this.errorMessage = assistantMessage.content;
          }

          this.messages = [...this.messages];
          this.changeDetector.detectChanges();
        },
      });
  }

  formatMessage(content: string): SafeHtml {
    if (!content) {
      return '';
    }

    let html = content
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');

    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/(?:^|\n)[*-] (.+)/g, '<br>&bull; $1');
    html = html.replace(/\n/g, '<br>');

    return this.sanitizer.bypassSecurityTrustHtml(html);
  }

  private getErrorMessage(error: unknown): string {
    if (error instanceof TimeoutError) {
      return 'The request took longer than 60 seconds. Please try again.';
    }

    if (error instanceof HttpErrorResponse) {
      const detail = error.error?.detail;

      if (typeof detail === 'string' && detail.trim()) {
        return detail;
      }

      if (error.status === 0) {
        return 'Could not connect to the API. Check the backend and proxy configuration.';
      }

      return `The API request failed with HTTP ${error.status}. Please try again.`;
    }

    return 'An unexpected error occurred while processing your question.';
  }

  newChat(): void {
    this.messages = [];
    this.question = '';
    this.errorMessage = '';
    this.loading = false;
    this.activePage = 'assistant';
  }

  setPage(page: string): void {
    this.activePage = page;
  }

  get currentPageTitle(): string {
    const titles: Record<string, string> = {
      overview: 'Overview',
      assistant: 'AI Assistant',
      traces: 'Agent Execution',
      data: 'Data Explorer',
      evidence: 'Knowledge & Evidence',
      evaluation: 'Evaluation & Verification',
    };

    return titles[this.activePage] || 'AI Assistant';
  }

  trackMessage(index: number): number {
    return index;
  }

  trackSource(index: number, source: SourceDocument): string {
    return (
      source.chunk_id ||
      source.document_id ||
      source.filename ||
      String(index)
    );
  }
}
