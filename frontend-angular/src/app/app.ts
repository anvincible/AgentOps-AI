
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
  business_summary?: {
    verified: boolean;
    validated_component_count: number;
    component_count: number;
    coverage_status: 'complete' | 'partial' | 'insufficient_evidence' | 'invalid';
    analysis_consistent: boolean;
    consistency_scope: string;
    component_queries: { area: string; status: string; sql_validated: boolean; result_nonempty: boolean }[];
    coverage: { area: string; status: string }[];
    issues: string[];
  };
}

interface ClarificationContext {
  original_question: string;
  kind: string;
  options: string[];
  prompt: string;
}

interface AskRequest {
  question: string;
  clarification_context?: ClarificationContext;
}

type ReportType = 'business_performance' | 'sales_analysis' | 'campaign_performance';
type ReportFormat = 'pdf' | 'xlsx';

interface AnalysisChart {
  type: 'bar' | 'line';
  metric: string;
  labels: string[];
  series: { name: string; metric?: string; values: number[] }[];
}

interface AnalysisResult {
  status: 'complete' | 'partial' | 'insufficient_evidence';
  summary: string;
  insights: string[];
  chart: AnalysisChart | null;
  evidence: { source?: string; query_intent?: string; validated?: boolean; row_count?: number };
  coverage?: { area: string; status: string }[];
  limitations: string[];
}

interface AskResponse {
  question?: string;
  route?: string;
  answer?: string;
  sources?: SourceDocument[];
  verification?: VerificationResult;
  clarification?: ClarificationContext | null;
  analysis?: AnalysisResult | null;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  route?: string;
  sources?: SourceDocument[];
  verification?: VerificationResult;
  clarification?: ClarificationContext;
  analysis?: AnalysisResult;
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
  pendingClarification: ClarificationContext | null = null;
  reportType: ReportType = 'business_performance';
  reportFormat: ReportFormat = 'pdf';
  reportLoading = false;
  reportError = '';
  private chatGeneration = 0;

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

  downloadReport(): void {
    if (this.reportLoading) {
      return;
    }
    this.reportLoading = true;
    this.reportError = '';
    this.http
      .post('/api/reports', {
        report_type: this.reportType,
        format: this.reportFormat,
      }, {
        observe: 'response',
        responseType: 'blob',
      })
      .pipe(timeout(120000), finalize(() => {
        this.reportLoading = false;
        this.changeDetector.detectChanges();
      }))
      .subscribe({
        next: (response) => {
          const blob = response.body;
          if (!blob || blob.size === 0) {
            this.reportError = 'The report response was empty. Please try again.';
            return;
          }
          const filename = this.reportFilename(response.headers.get('content-disposition'));
          const objectUrl = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = objectUrl;
          link.download = filename;
          link.style.display = 'none';
          document.body.appendChild(link);
          link.click();
          link.remove();
          URL.revokeObjectURL(objectUrl);
        },
        error: (error: unknown) => {
          void this.getReportErrorMessage(error).then((message) => {
            this.reportError = message;
            this.changeDetector.detectChanges();
          });
        },
      });
  }

  private async getReportErrorMessage(error: unknown): Promise<string> {
    const fallback = 'Could not generate the report. Check the API connection and try again.';
    if (!(error instanceof HttpErrorResponse)) {
      return fallback;
    }

    if (error.error instanceof Blob && error.error.type.includes('json')) {
      try {
        const body = JSON.parse(await error.error.text()) as { detail?: unknown };
        if (typeof body.detail === 'string' && body.detail.trim()) {
          return body.detail;
        }
      } catch {
        return fallback;
      }
    }

    const detail = error.error?.detail;
    return typeof detail === 'string' && detail.trim() ? detail : fallback;
  }

  private reportFilename(contentDisposition: string | null): string {
    const match = contentDisposition?.match(/filename\s*=\s*"?([^";]+)"?/i);
    return match?.[1]?.trim() || `novamart-report.${this.reportFormat}`;
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

    const clarificationContext = this.pendingClarification;
    const shouldSendClarificationContext =
      clarificationContext !== null &&
      this.isClarificationReply(question, clarificationContext);
    this.pendingClarification = null;
    const request: AskRequest = { question };
    if (shouldSendClarificationContext && clarificationContext) {
      request.clarification_context = clarificationContext;
    }
    const generation = this.chatGeneration;

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
      .post<AskResponse>('/api/ask', request)
      .pipe(
        timeout(60000),
        finalize(() => {
          if (generation !== this.chatGeneration) {
            return;
          }
          assistantMessage.pending = false;
          this.loading = false;
          this.messages = [...this.messages];
          this.changeDetector.detectChanges();
        }),
      )
      .subscribe({
        next: (response) => {
          if (generation !== this.chatGeneration) {
            return;
          }
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
          assistantMessage.analysis = response?.analysis ?? undefined;
          const clarification = response?.clarification;
          if (
            response?.route === 'CLARIFY' &&
            this.isClarificationContext(clarification)
          ) {
            assistantMessage.clarification = clarification;
            this.pendingClarification = clarification;
          } else {
            this.pendingClarification = null;
          }
          assistantMessage.pending = false;
          this.backendOnline = true;
          this.messages = [...this.messages];
          this.changeDetector.detectChanges();
        },

        error: (error: unknown) => {
          if (generation !== this.chatGeneration) {
            return;
          }
          assistantMessage.content = this.getErrorMessage(error);
          assistantMessage.sources = [];
          assistantMessage.verification = undefined;
          assistantMessage.pending = false;

          if (error instanceof HttpErrorResponse && error.status === 0) {
            this.backendOnline = false;
            this.messages = this.messages.filter(
              (message) => message !== assistantMessage,
            );
            this.errorMessage =
              'Cannot reach the backend. Check that FastAPI and the Angular proxy are running.';
          } else {
            this.backendOnline = true;
            this.errorMessage = '';
          }

          this.messages = [...this.messages];
          this.changeDetector.detectChanges();
        },
      });
  }

  selectClarificationOption(option: string): void {
    const clarification = this.pendingClarification;
    if (this.loading || !clarification?.options.includes(option)) {
      return;
    }

    this.question = clarification.kind === 'business_summary_period'
      ? option
      : `By ${option}`;
    this.sendQuestion();
  }

  formatClarificationOption(option: string): string {
    return option.replace(/\b\w/g, (character) => character.toUpperCase());
  }

  chartValue(chart: AnalysisChart, index: number, seriesIndex = 0): number {
    return chart.series[seriesIndex]?.values[index] ?? 0;
  }

  formatMetric(metric: string): string {
    return metric.replaceAll('_', ' ');
  }

  chartBarWidth(chart: AnalysisChart, index: number, seriesIndex = 0): number {
    const values = chart.series[seriesIndex]?.values ?? [];
    const max = Math.max(...values.map((value) => Math.abs(value)), 0);
    return max === 0 ? 0 : Math.max(2, Math.abs(this.chartValue(chart, index, seriesIndex)) / max * 100);
  }

  lineChartPoints(chart: AnalysisChart): string {
    const values = chart.series[0]?.values ?? [];
    if (!values.length) return '';
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    return values.map((value, index) => {
      const x = values.length === 1 ? 50 : 5 + index * 90 / (values.length - 1);
      const y = 90 - (value - min) / span * 80;
      return `${x},${y}`;
    }).join(' ');
  }

  lineChartY(chart: AnalysisChart, index: number): number {
    const values = chart.series[0]?.values ?? [];
    const min = Math.min(...values);
    const max = Math.max(...values);
    return values.length ? 90 - (this.chartValue(chart, index) - min) / (max - min || 1) * 80 : 90;
  }

  lineChartX(chart: AnalysisChart, index: number): number {
    const count = chart.series[0]?.values.length ?? 0;
    return count <= 1 ? 50 : 5 + index * 90 / (count - 1);
  }

  private isClarificationContext(
    value: unknown,
  ): value is ClarificationContext {
    if (!value || typeof value !== 'object') {
      return false;
    }

    const context = value as Partial<ClarificationContext>;
    return (
      typeof context.original_question === 'string' &&
      typeof context.kind === 'string' &&
      typeof context.prompt === 'string' &&
      Array.isArray(context.options) &&
      context.options.every((option) => typeof option === 'string')
    );
  }

  private isClarificationReply(
    reply: string,
    context: ClarificationContext,
  ): boolean {
    if (context.kind === 'campaign_comparison_targets') {
      const match = reply.match(
        /^\s*(?:compare\s+)?(?:campaign\s+)?(CMP-\d+)\s*(?:,|and|&)\s*(?:campaign\s+)?(CMP-\d+)\s*[.!]?\s*$/i,
      );
      return Boolean(match && match[1].toUpperCase() !== match[2].toUpperCase());
    }
    const normalized = this.normalizeClarificationText(reply);
    if (!normalized || normalized.split(' ').length > 6) {
      return false;
    }

    if (context.kind === 'business_summary_period') {
      const original = this.normalizeClarificationText(context.original_question);
      const requestsSummary =
        /\b(?:summarize|summarise|summary|overview|snapshot)\b/.test(original) ||
        original.includes('business performance');
      const hasBusinessScope = /\b(?:novamart|business|overall)\b/.test(original);
      const namesSpecificEntity =
        /\b(?:campaign|product|customer|return|seller|shipment|payment|ticket)\b/.test(original);
      const hasBusinessSummaryScope =
        requestsSummary && hasBusinessScope && !namesSpecificEntity;
      const hasPeriod =
        /\b20\d{2}\b/.test(original) ||
        /\b(?:last|past|previous|rolling) (?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve) (?:days?|weeks?|months?|quarters?|years?)\b/.test(original) ||
        /\b(?:last|previous) year\b/.test(original) ||
        /\b(?:monthly|weekly|quarterly|yearly|annually|by month|by quarter|over time)\b/.test(original);
      const optionsAreExpected = context.options.some(
        (option) => this.normalizeClarificationText(option) === 'all time summary',
      );
      const hasAllTimeScope = /\b(?:all time|unfiltered)\b/.test(normalized);
      const isOfferedOption = context.options.some(
        (option) => this.normalizeClarificationText(option) === normalized,
      );
      const affirmative = /\b(?:yes|yeah|sure|fine|acceptable|okay|ok|use|accept|works|good)\b/.test(normalized);
      const negative = /\b(?:no|not|never|dont|don t|without)\b/.test(normalized);
      return Boolean(
        hasBusinessSummaryScope && hasPeriod && optionsAreExpected && hasAllTimeScope &&
        (isOfferedOption || (affirmative && !negative)),
      );
    }

    const aliases: Record<string, Record<string, string[]>> = {
      product_ranking_metric: {
        revenue: ['revenue', 'sales'],
        quantity: ['quantity', 'units', 'quantity sold', 'units sold'],
      },
      customer_distribution_dimension: {
        segment: ['segment', 'customer segment'],
        location: ['location', 'locations'],
        city: ['city'],
        state: ['state'],
        country: ['country'],
        'loyalty tier': ['loyalty', 'loyalty tier'],
        'acquisition channel': ['acquisition channel', 'channel'],
      },
      date_range: {
        'previous calendar year': [
          'calendar year',
          'previous calendar year',
          'last calendar year',
        ],
        'rolling 12 months': ['rolling 12 months', 'rolling year', '12 months'],
      },
    };

    const matchesAlias = (alias: string): boolean => {
      const normalizedAlias = this.normalizeClarificationText(alias);
      return [
        normalizedAlias,
        `by ${normalizedAlias}`,
        `use ${normalizedAlias}`,
        `rank by ${normalizedAlias}`,
        `group by ${normalizedAlias}`,
      ].includes(normalized);
    };

    return context.options.some((option) => {
      const optionAliases = aliases[context.kind]?.[option] ?? [option];
      return optionAliases.some(matchesAlias);
    });
  }

  private normalizeClarificationText(value: string): string {
    return value.toLowerCase().replace(/[^a-z0-9 ]/g, ' ').trim().replace(/\s+/g, ' ');
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
    this.chatGeneration += 1;
    this.messages = [];
    this.question = '';
    this.errorMessage = '';
    this.pendingClarification = null;
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
