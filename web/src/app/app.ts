import { Component, inject } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive, Router } from '@angular/router';
import { AuthService } from './services/auth.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    @if (showNav()) {
      <nav class="navbar">
        <div class="nav-brand">AI News Platform</div>
        <div class="nav-links">
          <a routerLink="/dashboard" routerLinkActive="active">Dashboard</a>
          <a routerLink="/archive" routerLinkActive="active">Archivo</a>
          <a routerLink="/search" routerLinkActive="active">Buscar</a>
          <a routerLink="/analytics" routerLinkActive="active">Analytics</a>
          <button class="logout-btn" (click)="onLogout()">Salir</button>
        </div>
      </nav>
    }

    <main [class.with-nav]="showNav()">
      <router-outlet />
    </main>
  `,
  styles: [`
    :host {
      display: block;
      font-family: system-ui, -apple-system, sans-serif;
      color: #1a1a2e;
    }
    .navbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      height: 52px;
      background: #1e293b;
      color: white;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .nav-brand {
      font-weight: 700;
      font-size: 1rem;
      letter-spacing: -0.3px;
    }
    .nav-links {
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .nav-links a {
      color: #94a3b8;
      text-decoration: none;
      font-size: 0.85rem;
      font-weight: 500;
      padding: 6px 12px;
      border-radius: 4px;
      transition: color 0.15s, background 0.15s;
    }
    .nav-links a:hover {
      color: white;
      background: rgba(255, 255, 255, 0.1);
    }
    .nav-links a.active {
      color: white;
      background: rgba(255, 255, 255, 0.15);
    }
    .logout-btn {
      color: #94a3b8;
      background: none;
      border: 1px solid #475569;
      font-size: 0.8rem;
      padding: 5px 12px;
      border-radius: 4px;
      cursor: pointer;
      margin-left: 8px;
      transition: color 0.15s, border-color 0.15s;
    }
    .logout-btn:hover {
      color: white;
      border-color: #94a3b8;
    }
    main.with-nav {
      max-width: 800px;
      margin: 0 auto;
      padding: 20px;
    }
    @media (max-width: 640px) {
      .navbar {
        padding: 0 12px;
        height: 48px;
      }
      .nav-brand { font-size: 0.9rem; }
      .nav-links a { font-size: 0.78rem; padding: 5px 8px; }
      .logout-btn { font-size: 0.75rem; padding: 4px 8px; }
      main.with-nav { padding: 12px; }
    }
  `],
})
export class App {
  private auth = inject(AuthService);
  private router = inject(Router);

  showNav(): boolean {
    return this.auth.isAuthenticated() && !this.router.url.includes('/login');
  }

  onLogout() {
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}
