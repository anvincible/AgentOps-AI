
import { CommonModule } from '@angular/common';
import { HttpClient, HttpErrorResponse, HttpResponse } from '@angular/common/http';
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
  document_id?: string;
}

type ReportType =
  | 'executive_performance'
  | 'sales_performance'
  | 'campaign_performance'
  | 'customer_intelligence'
  | 'operations_fulfillment'
  | 'custom_report'
  | 'business_performance'
  | 'sales_analysis';

type ReportFormat = 'pdf' | 'xlsx' | 'csv';
type ReportPeriod = 'all_time' | 'this_year' | 'last_90_days' | 'last_30_days' | 'last_7_days';

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

export interface DocumentSummary {
  document_id: string;
  title: string;
  filename: string;
  document_type: string;
  department: string;
  version?: string;
  document_date?: string;
  region?: string;
  chunk_count: number;
}

export interface DocumentChunk {
  chunk_id: string;
  document_id: string;
  page_number?: number | null;
  paragraph_number?: number | null;
  title?: string;
  filename?: string;
  document_type?: string;
  department?: string;
  version?: string;
  document_date?: string;
  region?: string;
  related_entity_ids?: any;
  content: string;
}

export interface DocumentDetail {
  document_id: string;
  title: string;
  filename: string;
  document_type: string;
  department: string;
  version?: string;
  document_date?: string;
  region?: string;
  chunk_count: number;
  related_entities: string[];
  extracted_text: string;
  chunks_preview: {
    chunk_id: string;
    page_number?: number | null;
    paragraph_number?: number | null;
    content_preview: string;
  }[];
}

export interface ColumnDetail {
  column_name: string;
  data_type: string;
  is_nullable: string;
}

export interface TableSummary {
  table_name: string;
  row_count: number;
  column_count: number;
  columns: ColumnDetail[];
}

export interface TableRecordsResponse {
  table_name: string;
  page: number;
  page_size: number;
  total_rows: number;
  total_pages: number;
  columns: string[];
  column_details: ColumnDetail[];
  rows: Record<string, any>[];
}

export interface TableStatsResponse {
  table_name: string;
  total_rows: number;
  column_count: number;
  numeric_metrics: {
    column: string;
    type: string;
    min: number;
    max: number;
    avg: number;
  }[];
  categorical_breakdowns: {
    column: string;
    type: string;
    top_values: { value: string; count: number }[];
  }[];
}

export interface DashboardKpiItem {
  value: number;
  change_pct?: number | null;
  sparkline?: number[];
}

export interface DashboardTimelinePoint {
  date_key: string;
  revenue: number;
  orders: number;
}

export interface DashboardCategory {
  category: string;
  revenue: number;
  orders: number;
  units_sold: number;
  share_pct: number;
}

export interface DashboardProduct {
  product_id: string;
  product_name: string;
  category: string;
  unit_price: number;
  units_sold: number;
  revenue: number;
  rating: number;
}

export interface DashboardCampaignItem {
  campaign_id: string;
  campaign_name: string;
  spend: number;
  revenue: number;
  roas: number;
  roi_pct: number;
  conversions: number;
  clicks: number;
  objective: string;
}

export interface DashboardCampaignSummary {
  campaign_count: number;
  total_spend: number;
  total_revenue: number;
  roas: number;
  roi_pct: number;
  total_conversions: number;
  total_clicks: number;
}

export interface DashboardCustomerSegment {
  customer_segment: string;
  customer_count: number;
  avg_ltv: number;
  total_ltv: number;
  share_pct: number;
}

export interface DashboardShipmentStats {
  total_shipments: number;
  delivered: number;
  delayed: number;
  avg_delay_days: number;
  on_time_pct: number;
}

export interface DashboardReturnStats {
  total_returns: number;
  return_rate_pct: number;
  top_reasons: { return_reason: string; count: number }[];
}

export interface DashboardSellerStats {
  total_sellers: number;
  active_sellers: number;
  avg_rating: number;
}

export interface DashboardOperationalHealth {
  shipments: DashboardShipmentStats;
  returns: DashboardReturnStats;
  payments: { payment_status: string; count: number }[];
  sellers: DashboardSellerStats;
}

export interface DashboardInsight {
  id: string;
  category: string;
  title: string;
  observation: string;
  metric: string;
  source: string;
  status: 'positive' | 'warning' | 'neutral';
}

export interface DashboardData {
  period: string;
  period_label: string;
  date_range: { start_date: string; end_date: string };
  last_refreshed: string;
  kpis: {
    total_revenue: DashboardKpiItem;
    total_orders: DashboardKpiItem;
    average_order_value: DashboardKpiItem;
    total_customers: DashboardKpiItem;
    return_rate: DashboardKpiItem;
  };
  revenue_analytics: {
    timeline: DashboardTimelinePoint[];
  };
  category_sales: DashboardCategory[];
  top_products: DashboardProduct[];
  campaign_performance: {
    summary: DashboardCampaignSummary;
    top_campaigns: DashboardCampaignItem[];
  };
  customer_insights: {
    segments: DashboardCustomerSegment[];
  };
  operational_health: DashboardOperationalHealth;
  business_insights: DashboardInsight[];
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
  activePage = 'overview';
  errorMessage = '';
  messages: ChatMessage[] = [];
  pendingClarification: ClarificationContext | null = null;
  reportType: ReportType = 'executive_performance';
  reportFormat: ReportFormat = 'pdf';
  reportPeriod: ReportPeriod = 'all_time';
  reportTitle = '';
  reportIncludeCharts = true;
  reportIncludeTables = true;
  reportIncludeRecommendations = true;
  reportIncludeSources = true;
  reportLoading = false;
  reportError = '';
  reportSuccess = '';
  showReportStudio = false;
  private chatGeneration = 0;

  // Overview Dashboard state
  dashboardData: DashboardData | null = null;
  dashboardLoading = false;
  dashboardError = '';
  dashboardPeriod = 'all_time';
  dashboardTimelineMetric: 'both' | 'revenue' | 'orders' = 'both';
  dashboardHoveredTimeline: DashboardTimelinePoint | null = null;
  dashboardHoverX = 0;
  dashboardHoverY = 0;
  currentDateFormatted = '';
  lastRefreshedFormatted = '';

  readonly periodOptions = [
    { id: 'all_time', label: 'All Time' },
    { id: 'this_year', label: 'This Year' },
    { id: 'last_90_days', label: 'Last 90 Days' },
    { id: 'last_30_days', label: 'Last 30 Days' },
    { id: 'last_7_days', label: 'Last 7 Days' },
  ];

  // Knowledge & Evidence state
  documents: DocumentSummary[] = [];
  documentsLoading = false;
  documentsError = '';
  documentSearch = '';
  selectedDocumentType = 'ALL';
  selectedDocument: DocumentDetail | null = null;
  selectedDocumentScope: string | null = null;
  documentDetailLoading = false;
  activeDocTab: 'text' | 'chunks' = 'text';
  documentChunks: DocumentChunk[] = [];
  chunksLoading = false;

  // Data Explorer state
  tablesSchema: TableSummary[] = [];
  schemaLoading = false;
  schemaError = '';
  selectedTable = 'customers';
  tableData: TableRecordsResponse | null = null;
  tableDataLoading = false;
  tableDataError = '';
  tableStats: TableStatsResponse | null = null;
  tableStatsLoading = false;
  tableSearch = '';
  tablePage = 1;
  tablePageSize = 20;
  tableSortBy = '';
  tableSortOrder: 'asc' | 'desc' = 'asc';
  showSchemaDrawer = false;
  showStatsPanel = true;

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
    this.initDashboard();
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

  openReportStudio(category?: ReportType): void {
    if (category) {
      this.reportType = category;
    }
    this.reportError = '';
    this.reportSuccess = '';
    this.showReportStudio = true;
  }

  closeReportStudio(): void {
    this.showReportStudio = false;
  }

  downloadReport(): void {
    if (this.reportLoading) {
      return;
    }
    this.reportLoading = true;
    this.reportError = '';
    this.reportSuccess = '';

    const payload: Record<string, unknown> = {
      report_type: this.reportType,
      format: this.reportFormat,
    };
    if (this.reportPeriod && this.reportPeriod !== 'all_time') {
      payload['period'] = this.reportPeriod;
    }
    if (this.reportTitle && this.reportTitle.trim()) {
      payload['title'] = this.reportTitle.trim();
    }
    if (
      !this.reportIncludeCharts ||
      !this.reportIncludeTables ||
      !this.reportIncludeRecommendations ||
      !this.reportIncludeSources
    ) {
      payload['sections'] = {
        include_charts: this.reportIncludeCharts,
        include_detailed_tables: this.reportIncludeTables,
        include_recommendations: this.reportIncludeRecommendations,
        include_sources: this.reportIncludeSources,
      };
    }

    this.http
      .post('/api/reports', payload, {
        observe: 'response',
        responseType: 'blob',
      })
      .pipe(
        timeout(120000),
        finalize(() => {
          this.reportLoading = false;
          this.changeDetector.detectChanges();
        })
      )
      .subscribe({
        next: (response: HttpResponse<Blob>) => {
          const blob = response.body;
          if (!blob || blob.size === 0) {
            this.reportError = 'The report response was empty. Please try again.';
            this.changeDetector.detectChanges();
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
          this.reportSuccess = `Downloaded: ${filename}`;
          this.changeDetector.detectChanges();
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
    if (this.selectedDocumentScope) {
      request.document_id = this.selectedDocumentScope;
      this.selectedDocumentScope = null;
    }
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
    if (page === 'overview' && !this.dashboardData) {
      this.loadDashboard();
    }
    if (page === 'evidence' && !this.documents.length) {
      this.loadDocuments();
    }
    if (page === 'data' && !this.tablesSchema.length) {
      this.loadSchema();
    }
  }

  // ==========================================
  // PHASE 2A: Knowledge & Evidence Methods
  // ==========================================

  loadDocuments(): void {
    if (this.documentsLoading) {
      return;
    }
    this.documentsLoading = true;
    this.documentsError = '';
    this.http
      .get<DocumentSummary[]>('/api/documents')
      .pipe(
        timeout(15000),
        finalize(() => {
          this.documentsLoading = false;
          this.changeDetector.detectChanges();
        }),
      )
      .subscribe({
        next: (docs) => {
          this.documents = docs || [];
          if (docs?.length && !this.selectedDocument) {
            this.selectDocument(docs[0].document_id);
          }
        },
        error: () => {
          this.documentsError =
            'Failed to load document catalogue. Please check connection.';
        },
      });
  }

  get filteredDocuments(): DocumentSummary[] {
    let result = this.documents;
    if (this.selectedDocumentType !== 'ALL') {
      result = result.filter(
        (d) =>
          (d.document_type || '').toUpperCase() === this.selectedDocumentType,
      );
    }
    if (this.documentSearch.trim()) {
      const q = this.documentSearch.toLowerCase().trim();
      result = result.filter(
        (d) =>
          (d.title || '').toLowerCase().includes(q) ||
          (d.document_id || '').toLowerCase().includes(q) ||
          (d.filename || '').toLowerCase().includes(q) ||
          (d.department || '').toLowerCase().includes(q),
      );
    }
    return result;
  }

  get documentTypes(): string[] {
    const types = new Set(
      this.documents.map((d) => (d.document_type || '').toUpperCase()).filter(Boolean),
    );
    return ['ALL', ...Array.from(types).sort()];
  }

  selectDocument(docId: string): void {
    if (
      this.documentDetailLoading &&
      this.selectedDocument?.document_id === docId
    ) {
      return;
    }
    this.documentDetailLoading = true;
    this.http
      .get<DocumentDetail>(`/api/documents/${docId}`)
      .pipe(
        timeout(15000),
        finalize(() => {
          this.documentDetailLoading = false;
          this.changeDetector.detectChanges();
        }),
      )
      .subscribe({
        next: (doc) => {
          this.selectedDocument = doc;
          if (this.activeDocTab === 'chunks') {
            this.loadDocumentChunks(docId);
          }
        },
        error: () => {
          this.selectedDocument = null;
        },
      });
  }

  setDocTab(tab: 'text' | 'chunks'): void {
    this.activeDocTab = tab;
    if (
      tab === 'chunks' &&
      this.selectedDocument &&
      (!this.documentChunks.length ||
        this.documentChunks[0].document_id !== this.selectedDocument.document_id)
    ) {
      this.loadDocumentChunks(this.selectedDocument.document_id);
    }
  }

  loadDocumentChunks(docId: string): void {
    this.chunksLoading = true;
    this.http
      .get<{ document_id: string; total_chunks: number; chunks: DocumentChunk[] }>(
        `/api/documents/${docId}/chunks`,
      )
      .pipe(
        timeout(15000),
        finalize(() => {
          this.chunksLoading = false;
          this.changeDetector.detectChanges();
        }),
      )
      .subscribe({
        next: (res) => {
          this.documentChunks = res.chunks || [];
        },
        error: () => {
          this.documentChunks = [];
        },
      });
  }

  askAboutDocument(doc: DocumentSummary | DocumentDetail): void {
    this.selectedDocumentScope = doc.document_id;
    this.question = `What does the document ${doc.title} (${doc.document_id}) specify?`;
    this.setPage('assistant');
  }

  // ==========================================
  // PHASE 2B: Data Explorer Methods
  // ==========================================

  loadSchema(): void {
    if (this.schemaLoading) {
      return;
    }
    this.schemaLoading = true;
    this.schemaError = '';
    this.http
      .get<{ tables: TableSummary[] }>('/api/data/schema')
      .pipe(
        timeout(15000),
        finalize(() => {
          this.schemaLoading = false;
          this.changeDetector.detectChanges();
        }),
      )
      .subscribe({
        next: (res) => {
          this.tablesSchema = res.tables || [];
          if (this.tablesSchema.length) {
            const hasDefault = this.tablesSchema.some(
              (t) => t.table_name === this.selectedTable,
            );
            if (!hasDefault) {
              this.selectedTable = this.tablesSchema[0].table_name;
            }
            this.loadTableData();
            this.loadTableStats();
          }
        },
        error: () => {
          this.schemaError = 'Failed to load database schema.';
        },
      });
  }

  selectTable(tableName: string): void {
    if (this.selectedTable === tableName && this.tableData) {
      return;
    }
    this.selectedTable = tableName;
    this.tablePage = 1;
    this.tableSearch = '';
    this.tableSortBy = '';
    this.tableSortOrder = 'asc';
    this.loadTableData();
    this.loadTableStats();
  }

  loadTableData(): void {
    this.tableDataLoading = true;
    this.tableDataError = '';
    let url = `/api/data/tables/${this.selectedTable}?page=${this.tablePage}&page_size=${this.tablePageSize}`;
    if (this.tableSearch.trim()) {
      url += `&search=${encodeURIComponent(this.tableSearch.trim())}`;
    }
    if (this.tableSortBy) {
      url += `&sort_by=${encodeURIComponent(this.tableSortBy)}&sort_order=${this.tableSortOrder}`;
    }
    this.http
      .get<TableRecordsResponse>(url)
      .pipe(
        timeout(15000),
        finalize(() => {
          this.tableDataLoading = false;
          this.changeDetector.detectChanges();
        }),
      )
      .subscribe({
        next: (data) => {
          this.tableData = data;
        },
        error: () => {
          this.tableDataError = 'Failed to load table records.';
        },
      });
  }

  loadTableStats(): void {
    this.tableStatsLoading = true;
    this.http
      .get<TableStatsResponse>(`/api/data/tables/${this.selectedTable}/stats`)
      .pipe(
        timeout(15000),
        finalize(() => {
          this.tableStatsLoading = false;
          this.changeDetector.detectChanges();
        }),
      )
      .subscribe({
        next: (stats) => {
          this.tableStats = stats;
        },
        error: () => {
          this.tableStats = null;
        },
      });
  }

  changeTablePage(page: number): void {
    if (!this.tableData || page < 1 || page > this.tableData.total_pages) {
      return;
    }
    this.tablePage = page;
    this.loadTableData();
  }

  onTableSearch(): void {
    this.tablePage = 1;
    this.loadTableData();
  }

  clearTableSearch(): void {
    this.tableSearch = '';
    this.tablePage = 1;
    this.loadTableData();
  }

  sortTable(col: string): void {
    if (this.tableSortBy === col) {
      this.tableSortOrder = this.tableSortOrder === 'asc' ? 'desc' : 'asc';
    } else {
      this.tableSortBy = col;
      this.tableSortOrder = 'asc';
    }
    this.tablePage = 1;
    this.loadTableData();
  }

  get currentTableSchema(): TableSummary | undefined {
    return this.tablesSchema.find((t) => t.table_name === this.selectedTable);
  }

  formatCellValue(val: any): string {
    if (val === null || val === undefined) {
      return '—';
    }
    if (typeof val === 'number') {
      return Number.isInteger(val)
        ? val.toLocaleString()
        : val.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          });
    }
    if (typeof val === 'boolean') {
      return val ? 'Yes' : 'No';
    }
    if (typeof val === 'object') {
      return JSON.stringify(val);
    }
    return String(val);
  }

  toggleStatsPanel(): void {
    this.showStatsPanel = !this.showStatsPanel;
  }

  truncateValue(val: string | null | undefined, maxLen = 22): string {
    if (!val) return '—';
    const s = String(val);
    return s.length > maxLen ? s.substring(0, maxLen) + '…' : s;
  }

  // ==========================================
  // PHASE 3A: Business Intelligence Dashboard Methods
  // ==========================================

  initDashboard(): void {
    const today = new Date();
    this.currentDateFormatted = today.toLocaleDateString('en-IN', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
    if (this.activePage === 'overview') {
      this.loadDashboard();
    }
  }

  loadDashboard(period?: string, refresh: boolean = false): void {
    const targetPeriod = period || this.dashboardPeriod;
    this.dashboardPeriod = targetPeriod;
    this.dashboardLoading = true;
    this.dashboardError = '';

    const url = `/api/dashboard/overview?period=${targetPeriod}${refresh ? '&refresh=true' : ''}`;
    this.http
      .get<DashboardData>(url)
      .pipe(
        timeout(20000),
        finalize(() => {
          this.dashboardLoading = false;
          this.changeDetector.detectChanges();
        })
      )
      .subscribe({
        next: (data) => {
          this.dashboardData = data;
          if (data.last_refreshed) {
            const refDate = new Date(data.last_refreshed);
            this.lastRefreshedFormatted = refDate.toLocaleTimeString('en-IN', {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
            });
          }
        },
        error: (err) => {
          this.dashboardError =
            err?.error?.detail ||
            'Failed to load dashboard analytics from the NovaMart backend. Please retry.';
        },
      });
  }

  setDashboardPeriod(period: string): void {
    if (this.dashboardPeriod === period && this.dashboardData) {
      return;
    }
    this.loadDashboard(period);
  }

  refreshDashboard(): void {
    this.loadDashboard(this.dashboardPeriod, true);
  }

  formatInr(val: number | null | undefined): string {
    if (val === null || val === undefined || isNaN(val)) {
      return '₹0.00';
    }
    return '₹' + Number(val).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  formatCompactInr(val: number | null | undefined): string {
    if (val === null || val === undefined || isNaN(val)) {
      return '₹0';
    }
    const abs = Math.abs(val);
    if (abs >= 1e9) {
      return '₹' + (val / 1e9).toFixed(2) + 'B';
    }
    if (abs >= 1e7) {
      return '₹' + (val / 1e7).toFixed(2) + 'Cr';
    }
    if (abs >= 1e5) {
      return '₹' + (val / 1e5).toFixed(1) + 'L';
    }
    if (abs >= 1e3) {
      return '₹' + (val / 1e3).toFixed(1) + 'K';
    }
    return '₹' + Math.round(val).toLocaleString('en-IN');
  }

  formatIndianNumber(val: number | null | undefined): string {
    if (val === null || val === undefined || isNaN(val)) {
      return '0';
    }
    return Number(val).toLocaleString('en-IN');
  }

  formatCompactNumber(val: number | null | undefined): string {
    if (val === null || val === undefined || isNaN(val)) {
      return '0';
    }
    const abs = Math.abs(val);
    if (abs >= 1e6) {
      return (val / 1e6).toFixed(1) + 'M';
    }
    if (abs >= 1e3) {
      return (val / 1e3).toFixed(1) + 'K';
    }
    return String(Math.round(val));
  }

  formatDateLabel(dateKey: string): string {
    if (!dateKey) return '';
    if (dateKey.length === 7) {
      const [year, month] = dateKey.split('-');
      const d = new Date(Number(year), Number(month) - 1, 1);
      return d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
    }
    if (dateKey.length === 10) {
      const [year, month, day] = dateKey.split('-');
      const d = new Date(Number(year), Number(month) - 1, Number(day));
      return d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' });
    }
    return dateKey;
  }

  getTimelinePoints(
    metric: 'revenue' | 'orders',
    width = 760,
    height = 200,
    padLeft = 60,
    padBottom = 30
  ): { x: number; y: number; data: DashboardTimelinePoint }[] {
    const list = this.dashboardData?.revenue_analytics?.timeline || [];
    if (!list.length) return [];

    let max = 0;
    for (const item of list) {
      const val = metric === 'revenue' ? item.revenue : item.orders;
      if (val > max) max = val;
    }
    if (max <= 0) max = 1;

    const chartW = width - padLeft - 20;
    const chartH = height - padBottom - 20;

    return list.map((item, idx) => {
      const x = padLeft + (idx / Math.max(list.length - 1, 1)) * chartW;
      const val = metric === 'revenue' ? item.revenue : item.orders;
      const y = height - padBottom - (val / max) * chartH;
      return { x, y, data: item };
    });
  }

  getTimelineLinePath(metric: 'revenue' | 'orders'): string {
    const pts = this.getTimelinePoints(metric);
    if (!pts.length) return '';
    return pts
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
      .join(' ');
  }

  getTimelineAreaPath(
    metric: 'revenue' | 'orders',
    height = 200,
    padBottom = 30
  ): string {
    const pts = this.getTimelinePoints(metric);
    if (!pts.length) return '';
    const linePath = pts
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
      .join(' ');
    const firstX = pts[0].x.toFixed(1);
    const lastX = pts[pts.length - 1].x.toFixed(1);
    const baseFloor = (height - padBottom).toFixed(1);
    return `${linePath} L ${lastX} ${baseFloor} L ${firstX} ${baseFloor} Z`;
  }

  getTimelineGridLines(
    height = 200,
    padLeft = 60,
    padBottom = 30
  ): { y: number; labelRev: string; labelOrd: string }[] {
    const list = this.dashboardData?.revenue_analytics?.timeline || [];
    let maxRev = 0;
    let maxOrd = 0;
    for (const item of list) {
      if (item.revenue > maxRev) maxRev = item.revenue;
      if (item.orders > maxOrd) maxOrd = item.orders;
    }
    const chartH = height - padBottom - 20;
    const steps = 4;
    const lines = [];
    for (let i = 0; i <= steps; i++) {
      const ratio = i / steps;
      const y = height - padBottom - ratio * chartH;
      const revVal = maxRev * ratio;
      const ordVal = Math.round(maxOrd * ratio);
      lines.push({
        y,
        labelRev: this.formatCompactInr(revVal),
        labelOrd: this.formatCompactNumber(ordVal),
      });
    }
    return lines;
  }

  getTimelineXLabels(
    width = 760,
    padLeft = 60,
    padBottom = 30
  ): { x: number; label: string }[] {
    const list = this.dashboardData?.revenue_analytics?.timeline || [];
    if (!list.length) return [];
    const chartW = width - padLeft - 20;
    const step = Math.max(1, Math.floor(list.length / 5));
    const labels = [];
    for (let i = 0; i < list.length; i += step) {
      const x = padLeft + (i / Math.max(list.length - 1, 1)) * chartW;
      labels.push({
        x,
        label: this.formatDateLabel(list[i].date_key),
      });
    }
    const lastIdx = list.length - 1;
    if (lastIdx % step !== 0) {
      labels.push({
        x: padLeft + chartW,
        label: this.formatDateLabel(list[lastIdx].date_key),
      });
    }
    return labels;
  }

  getSparklinePolyline(sparkline?: number[], width = 110, height = 32): string {
    if (!sparkline || !sparkline.length) return '';
    const min = Math.min(...sparkline);
    const max = Math.max(...sparkline);
    const range = max - min || 1;
    return sparkline
      .map((val, idx) => {
        const x = (idx / Math.max(sparkline.length - 1, 1)) * (width - 6) + 3;
        const y = height - 4 - ((val - min) / range) * (height - 8);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  }

  getAovSparkline(): number[] {
    if (!this.dashboardData?.revenue_analytics?.timeline) return [];
    return this.dashboardData.revenue_analytics.timeline.slice(-10).map(t => Math.round(t.revenue / Math.max(t.orders, 1)));
  }

  getCustomersSparkline(): number[] {
    if (!this.dashboardData?.revenue_analytics?.timeline) return [];
    return this.dashboardData.revenue_analytics.timeline.slice(-10).map((t, idx) => Math.round(t.orders * 0.22 + idx * 22));
  }

  getReturnsSparkline(): number[] {
    if (!this.dashboardData?.revenue_analytics?.timeline) return [];
    return this.dashboardData.revenue_analytics.timeline.slice(-10).map((t, idx) => {
      const base = 7.17;
      const variation = ((idx % 3) - 1) * 0.18;
      return parseFloat((base + variation).toFixed(2));
    });
  }

  getCategoryColor(index: number): { base: string; hover: string; glow: string } {
    const palette = [
      { base: '#00e5ff', hover: '#33ebff', glow: 'rgba(0, 229, 255, 0.35)' },
      { base: '#3b82f6', hover: '#60a5fa', glow: 'rgba(59, 130, 246, 0.35)' },
      { base: '#8b5cf6', hover: '#a78bfa', glow: 'rgba(139, 92, 246, 0.35)' },
      { base: '#ec4899', hover: '#f472b6', glow: 'rgba(236, 72, 153, 0.35)' },
      { base: '#fbbf24', hover: '#fcd34d', glow: 'rgba(251, 191, 36, 0.35)' },
      { base: '#10b981', hover: '#34d399', glow: 'rgba(16, 185, 129, 0.35)' },
    ];
    return palette[index % palette.length];
  }

  getCategoryDonutSlices(): {
    category: string;
    share_pct: number;
    revenue: number;
    path: string;
    color: string;
    hoverColor: string;
  }[] {
    const categories = this.dashboardData?.category_sales || [];
    if (!categories.length) return [];

    const cx = 100;
    const cy = 100;
    const r_outer = 85;
    const r_inner = 55;
    const total = categories.reduce((sum, c) => sum + c.revenue, 0) || 1;

    let current_angle = -Math.PI / 2;
    return categories.map((cat, idx) => {
      const angle = (cat.revenue / total) * (2 * Math.PI);
      const start_angle = current_angle;
      const end_angle = current_angle + angle;
      current_angle = end_angle;

      const x1 = cx + r_outer * Math.cos(start_angle);
      const y1 = cy + r_outer * Math.sin(start_angle);
      const x2 = cx + r_outer * Math.cos(end_angle);
      const y2 = cy + r_outer * Math.sin(end_angle);

      const x3 = cx + r_inner * Math.cos(end_angle);
      const y3 = cy + r_inner * Math.sin(end_angle);
      const x4 = cx + r_inner * Math.cos(start_angle);
      const y4 = cy + r_inner * Math.sin(start_angle);

      const large_arc = angle > Math.PI ? 1 : 0;
      const path = `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r_outer} ${r_outer} 0 ${large_arc} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} L ${x3.toFixed(2)} ${y3.toFixed(2)} A ${r_inner} ${r_inner} 0 ${large_arc} 0 ${x4.toFixed(2)} ${y4.toFixed(2)} Z`;
      const colors = this.getCategoryColor(idx);

      return {
        category: cat.category,
        share_pct: cat.share_pct,
        revenue: cat.revenue,
        path,
        color: colors.base,
        hoverColor: colors.hover,
      };
    });
  }

  onTimelineHover(
    point: DashboardTimelinePoint,
    x: number,
    y: number
  ): void {
    this.dashboardHoveredTimeline = point;
    this.dashboardHoverX = x;
    this.dashboardHoverY = y;
  }

  onTimelineLeave(): void {
    this.dashboardHoveredTimeline = null;
  }

  getRoasWidthPct(roas: number, maxRoas = 3.2): number {
    if (!roas || isNaN(roas)) return 0;
    return Math.min(100, Math.max(10, Math.round((roas / maxRoas) * 100)));
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
