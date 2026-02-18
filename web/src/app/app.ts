import { Component, HostListener, inject, signal } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive, Router } from '@angular/router';
import { AuthService } from './services/auth.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    @if (showNav()) {
      <nav class="navbar">
        <div class="nav-brand">AI News Platform</div>
        <button class="hamburger" (click)="toggleMenu()">&#9776;</button>
        <div class="nav-links" [class.open]="menuOpen()">
          <a routerLink="/dashboard" routerLinkActive="active" (click)="onNavClick()">Dashboard</a>
          <a routerLink="/archive" routerLinkActive="active" (click)="onNavClick()">Archivo</a>
          <a routerLink="/search" routerLinkActive="active" (click)="onNavClick()">Buscar</a>
          <a routerLink="/analytics" routerLinkActive="active" (click)="onNavClick()">Analytics</a>
          <a routerLink="/chat" routerLinkActive="active" (click)="onNavClick()">Chat</a>
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
      font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif;
      color: #1d1d1f;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }
    .navbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      height: 44px;
      background: rgba(29, 29, 31, 0.96);
      backdrop-filter: saturate(180%) blur(20px);
      color: white;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .nav-brand {
      font-weight: 600;
      font-size: 0.9375rem;
      letter-spacing: -0.01em;
      color: #f5f5f7;
    }
    .nav-links {
      display: flex;
      align-items: center;
      gap: 2px;
    }
    .nav-links a {
      color: rgba(255, 255, 255, 0.56);
      text-decoration: none;
      font-size: 0.8125rem;
      font-weight: 400;
      padding: 6px 14px;
      border-radius: 6px;
      transition: color 0.2s, background 0.2s;
    }
    .nav-links a:hover {
      color: rgba(255, 255, 255, 0.88);
    }
    .nav-links a.active {
      color: #f5f5f7;
      background: rgba(255, 255, 255, 0.1);
      font-weight: 500;
    }
    .logout-btn {
      color: rgba(255, 255, 255, 0.48);
      background: none;
      border: none;
      font-size: 0.8125rem;
      padding: 6px 14px;
      border-radius: 6px;
      cursor: pointer;
      margin-left: 4px;
      transition: color 0.2s;
    }
    .logout-btn:hover {
      color: rgba(255, 255, 255, 0.88);
    }
    .hamburger {
      display: none;
      background: none;
      border: none;
      color: #f5f5f7;
      font-size: 1.25rem;
      cursor: pointer;
      padding: 4px 8px;
    }
    main.with-nav {
      max-width: 980px;
      margin: 0 auto;
      padding: 32px 24px;
    }
    @media (max-width: 640px) {
      .navbar {
        padding: 0 16px;
        height: 44px;
      }
      .nav-brand { font-size: 0.875rem; }
      .hamburger { display: block; }
      .nav-links {
        display: none;
        position: absolute;
        top: 44px;
        left: 0;
        right: 0;
        background: rgba(29, 29, 31, 0.98);
        backdrop-filter: saturate(180%) blur(20px);
        flex-direction: column;
        padding: 8px 16px 12px;
        gap: 2px;
      }
      .nav-links.open { display: flex; }
      .nav-links a { font-size: 0.8125rem; padding: 10px 16px; }
      .logout-btn { font-size: 0.8125rem; padding: 10px 16px; text-align: left; }
      main.with-nav { padding: 20px 16px; }
    }
  `],
})
export class App {
  private auth = inject(AuthService);
  private router = inject(Router);

  menuOpen = signal(false);

  showNav(): boolean {
    return this.auth.isAuthenticated() && !this.router.url.includes('/login');
  }

  toggleMenu() {
    this.menuOpen.update(v => !v);
  }

  onNavClick() {
    this.menuOpen.set(false);
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: Event) {
    const target = event.target as HTMLElement;
    if (!target.closest('.navbar')) {
      this.menuOpen.set(false);
    }
  }

  onLogout() {
    this.menuOpen.set(false);
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}
