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
    .hamburger {
      display: none;
      background: none;
      border: none;
      color: white;
      font-size: 1.4rem;
      cursor: pointer;
      padding: 4px 8px;
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
      .hamburger { display: block; }
      .nav-links {
        display: none;
        position: absolute;
        top: 48px;
        left: 0;
        right: 0;
        background: #1e293b;
        flex-direction: column;
        padding: 8px 12px;
        gap: 4px;
      }
      .nav-links.open { display: flex; }
      .nav-links a { font-size: 0.78rem; padding: 8px 12px; }
      .logout-btn { font-size: 0.75rem; padding: 4px 8px; }
      main.with-nav { padding: 12px; }
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
