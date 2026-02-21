import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, firstValueFrom } from 'rxjs';

interface TokenResponseV2 {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private tokenKey = 'ainews_token';
  private refreshKey = 'ainews_refresh_token';
  private expiryKey = 'ainews_token_expiry';

  login(password: string): Observable<TokenResponseV2> {
    return this.http
      .post<TokenResponseV2>('/api/auth/token', { password })
      .pipe(tap((res) => this.storeTokens(res)));
  }

  private refreshInProgress: Promise<boolean> | null = null;

  async refreshToken(): Promise<boolean> {
    if (this.refreshInProgress) return this.refreshInProgress;
    this.refreshInProgress = this.doRefresh();
    try {
      return await this.refreshInProgress;
    } finally {
      this.refreshInProgress = null;
    }
  }

  private async doRefresh(): Promise<boolean> {
    const refreshToken = localStorage.getItem(this.refreshKey);
    if (!refreshToken) return false;

    try {
      const res = await firstValueFrom(
        this.http.post<TokenResponseV2>('/api/auth/refresh', {
          refresh_token: refreshToken,
        })
      );
      this.storeTokens(res);
      return true;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'unknown';
      console.error('[AuthService] Token refresh failed:', msg);
      this.logout();
      return false;
    }
  }

  logout(): void {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.refreshKey);
    localStorage.removeItem(this.expiryKey);
  }

  getToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  isAuthenticated(): boolean {
    const token = this.getToken();
    if (!token) return false;
    const expiry = localStorage.getItem(this.expiryKey);
    if (expiry) {
      return parseInt(expiry, 10) > Date.now();
    }
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.exp * 1000 > Date.now();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'unknown';
      console.warn('[AuthService] JWT decode failed:', msg);
      return false;
    }
  }

  private storeTokens(res: TokenResponseV2): void {
    localStorage.setItem(this.tokenKey, res.access_token);
    localStorage.setItem(this.refreshKey, res.refresh_token);
    localStorage.setItem(
      this.expiryKey,
      (Date.now() + res.expires_in * 1000).toString()
    );
  }
}
