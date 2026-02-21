import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams, HttpResponse } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import {
  NewsItem,
  Briefing,
  PaginatedResponse,
  StatsSummary,
  StatsGroup,
  StatsDate,
} from '../models/news-item';

@Injectable({ providedIn: 'root' })
export class NewsService {
  private http = inject(HttpClient);
  private baseUrl = '/api';

  private toPaginated<T>(res: HttpResponse<T[]>): PaginatedResponse<T> {
    return {
      items: res.body ?? [],
      totalCount: parseInt(res.headers.get('X-Total-Count') ?? '0', 10),
    };
  }

  getTodayItems(params?: {
    limit?: number;
    offset?: number;
    topic?: string;
  }): Observable<PaginatedResponse<NewsItem>> {
    let httpParams = new HttpParams();
    if (params?.limit !== undefined) httpParams = httpParams.set('limit', params.limit);
    if (params?.offset !== undefined) httpParams = httpParams.set('offset', params.offset);
    if (params?.topic) httpParams = httpParams.set('topic', params.topic);
    return this.http
      .get<NewsItem[]>(`${this.baseUrl}/items/today`, {
        params: httpParams,
        observe: 'response',
      })
      .pipe(map((res) => this.toPaginated(res)));
  }

  getItems(params?: {
    source?: string;
    topic?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Observable<PaginatedResponse<NewsItem>> {
    let httpParams = new HttpParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          httpParams = httpParams.set(key, value.toString());
        }
      });
    }
    return this.http
      .get<NewsItem[]>(`${this.baseUrl}/items`, {
        params: httpParams,
        observe: 'response',
      })
      .pipe(map((res) => this.toPaginated(res)));
  }

  getBriefing(date: string): Observable<Briefing> {
    return this.http.get<Briefing>(`${this.baseUrl}/briefings/${date}`);
  }

  getBriefings(params?: {
    limit?: number;
    offset?: number;
  }): Observable<PaginatedResponse<Briefing>> {
    let httpParams = new HttpParams();
    if (params?.limit !== undefined) httpParams = httpParams.set('limit', params.limit);
    if (params?.offset !== undefined) httpParams = httpParams.set('offset', params.offset);
    return this.http
      .get<Briefing[]>(`${this.baseUrl}/briefings`, {
        params: httpParams,
        observe: 'response',
      })
      .pipe(map((res) => this.toPaginated(res)));
  }

  getTopics(): Observable<string[]> {
    return this.http
      .get<{ topics: string[] }>(`${this.baseUrl}/topics`)
      .pipe(map((response) => response.topics));
  }

  searchItems(params: {
    q: string;
    topic?: string;
    date_from?: string;
    date_to?: string;
    sort_by?: string;
    limit?: number;
    offset?: number;
  }): Observable<PaginatedResponse<NewsItem>> {
    let httpParams = new HttpParams().set('q', params.q);
    if (params.topic) httpParams = httpParams.set('topic', params.topic);
    if (params.date_from) httpParams = httpParams.set('date_from', params.date_from);
    if (params.date_to) httpParams = httpParams.set('date_to', params.date_to);
    if (params.sort_by) httpParams = httpParams.set('sort_by', params.sort_by);
    if (params.limit !== undefined) httpParams = httpParams.set('limit', params.limit.toString());
    if (params.offset !== undefined) httpParams = httpParams.set('offset', params.offset.toString());
    return this.http
      .get<NewsItem[]>(`${this.baseUrl}/search`, {
        params: httpParams,
        observe: 'response',
      })
      .pipe(map((res) => this.toPaginated(res)));
  }

  getStatsSummary(): Observable<StatsSummary> {
    return this.http.get<StatsSummary>(`${this.baseUrl}/stats/summary`);
  }

  getStatsBySource(): Observable<StatsGroup[]> {
    return this.http.get<StatsGroup[]>(`${this.baseUrl}/stats/by-source`);
  }

  getStatsByTopic(): Observable<StatsGroup[]> {
    return this.http.get<StatsGroup[]>(`${this.baseUrl}/stats/by-topic`);
  }

  getStatsByDate(days = 30): Observable<StatsDate[]> {
    return this.http.get<StatsDate[]>(`${this.baseUrl}/stats/by-date`, {
      params: new HttpParams().set('days', days),
    });
  }
}
