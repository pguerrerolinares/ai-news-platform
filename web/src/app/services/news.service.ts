import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { NewsItem, Briefing } from '../models/news-item';

@Injectable({ providedIn: 'root' })
export class NewsService {
  private http = inject(HttpClient);
  private baseUrl = '/api';

  getTodayItems(limit = 100): Observable<NewsItem[]> {
    return this.http.get<NewsItem[]>(`${this.baseUrl}/items/today`, {
      params: new HttpParams().set('limit', limit),
    });
  }

  getItems(params?: {
    source?: string;
    topic?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Observable<NewsItem[]> {
    let httpParams = new HttpParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          httpParams = httpParams.set(key, value.toString());
        }
      });
    }
    return this.http.get<NewsItem[]>(`${this.baseUrl}/items`, { params: httpParams });
  }

  getBriefing(date: string): Observable<Briefing> {
    return this.http.get<Briefing>(`${this.baseUrl}/briefings/${date}`);
  }

  getBriefings(): Observable<Briefing[]> {
    return this.http.get<Briefing[]>(`${this.baseUrl}/briefings`);
  }

  searchItems(params: {
    q: string;
    topic?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
  }): Observable<NewsItem[]> {
    let httpParams = new HttpParams().set('q', params.q);
    if (params.topic) httpParams = httpParams.set('topic', params.topic);
    if (params.date_from) httpParams = httpParams.set('date_from', params.date_from);
    if (params.date_to) httpParams = httpParams.set('date_to', params.date_to);
    if (params.limit) httpParams = httpParams.set('limit', params.limit.toString());
    return this.http.get<NewsItem[]>(`${this.baseUrl}/search`, { params: httpParams });
  }
}
