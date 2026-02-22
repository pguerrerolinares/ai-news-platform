import { Component, HostListener, inject, signal } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive, Router } from '@angular/router';
import { AuthService } from './services/auth.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    @if (showNav()) {
      <nav class="navbar">
        <div class="nav-brand">
          <span class="status-dot"></span>
          AI NEWS AGGREGATOR
        </div>
        <button class="hamburger" (click)="toggleMenu()" aria-label="Menu">
          <span class="hamburger-line"></span>
          <span class="hamburger-line"></span>
        </button>
        <div class="nav-links" [class.open]="menuOpen()">
          <a routerLink="/dashboard" routerLinkActive="active" (click)="onNavClick()">DASH</a>
          <a routerLink="/archive" routerLinkActive="active" (click)="onNavClick()">ARCHIVO</a>
          <a routerLink="/search" routerLinkActive="active" (click)="onNavClick()">BUSCAR</a>
          <a routerLink="/analytics" routerLinkActive="active" (click)="onNavClick()">STATS</a>
          <a routerLink="/chat" routerLinkActive="active" (click)="onNavClick()">CHAT</a>
          <button class="theme-toggle" (click)="cycleTheme()" [title]="'Tema: ' + currentTheme()">
            {{ currentTheme() === 'dark' ? 'LIGHT' : 'DARK' }}
          </button>
          <button class="logout-btn" (click)="onLogout()">SALIR</button>
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
      font-family: var(--font-body);
      color: var(--text-secondary);
    }
    .navbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 28px;
      height: 52px;
      background: var(--bg-surface);
      border-bottom: 1px solid var(--text-primary);
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .nav-brand {
      font-family: var(--font-heading);
      font-weight: 700;
      font-size: var(--text-sm);
      letter-spacing: -0.03em;
      color: var(--text-primary);
      text-transform: uppercase;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .status-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--ed-status-color);
      animation: pulse-dot 2s ease-in-out infinite;
    }
    .nav-links {
      display: flex;
      align-items: center;
      gap: 0;
    }
    .nav-links a {
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-muted);
      text-decoration: none;
      padding: 6px 14px;
      position: relative;
      transition: color 0.15s ease;
    }
    .nav-links a::after {
      content: '';
      position: absolute;
      bottom: -2px;
      left: 50%;
      transform: translateX(-50%);
      width: 0;
      height: 2px;
      background: var(--accent);
      transition: width 0.15s ease;
    }
    .nav-links a:hover {
      color: var(--text-primary);
    }
    .nav-links a:hover::after {
      width: 100%;
    }
    .nav-links a.active {
      color: var(--text-primary);
      font-weight: 600;
    }
    .nav-links a.active::after {
      width: 100%;
    }
    .theme-toggle {
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 500;
      letter-spacing: 0.08em;
      color: var(--text-muted);
      background: none;
      border: 1px solid var(--border);
      padding: 4px 10px;
      cursor: pointer;
      margin-left: 8px;
      transition: color 0.15s ease, border-color 0.15s ease;
    }
    .theme-toggle:hover {
      color: var(--text-primary);
      border-color: var(--text-primary);
    }
    .logout-btn {
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 500;
      letter-spacing: 0.08em;
      color: var(--text-muted);
      background: none;
      border: none;
      padding: 6px 10px;
      cursor: pointer;
      margin-left: 4px;
      transition: color 0.15s ease;
    }
    .logout-btn:hover {
      color: var(--accent);
    }
    .hamburger {
      display: none;
      flex-direction: column;
      gap: 4px;
      background: none;
      border: none;
      padding: 8px;
      cursor: pointer;
    }
    .hamburger-line {
      display: block;
      width: 18px;
      height: 1.5px;
      background: var(--text-primary);
    }
    main.with-nav {
      max-width: 1120px;
      margin: 0 auto;
      padding: 40px 32px;
    }
    @media (max-width: 640px) {
      .navbar {
        padding: 0 16px;
        height: 48px;
      }
      .nav-brand { font-size: 11px; }
      .hamburger { display: flex; }
      .nav-links {
        display: flex;
        flex-direction: column;
        position: absolute;
        top: 48px;
        left: 0;
        right: 0;
        background: var(--bg-surface);
        border-bottom: 1px solid var(--text-primary);
        padding: 8px 16px 12px;
        gap: 2px;
        z-index: 99;
        opacity: 0;
        visibility: hidden;
        transform: translateY(-6px);
        transition: opacity 0.18s ease, transform 0.18s ease, visibility 0.18s;
        pointer-events: none;
      }
      .nav-links.open {
        opacity: 1;
        visibility: visible;
        transform: translateY(0);
        pointer-events: auto;
      }
      .nav-links a {
        font-size: 11px;
        padding: 10px 16px;
        width: 100%;
      }
      .nav-links a::after { display: none; }
      .logout-btn { font-size: 11px; padding: 10px 16px; text-align: left; }
      .theme-toggle { margin: 4px 16px; }
      main.with-nav { padding: 24px 16px; }
    }
  `],
})
export class App {
  private auth = inject(AuthService);
  private router = inject(Router);

  menuOpen = signal(false);
  currentTheme = signal<'dark' | 'light'>(this.getInitialTheme());

  private getInitialTheme(): 'dark' | 'light' {
    const stored = localStorage.getItem('theme');
    if (stored === 'light') return 'light';
    return 'dark';
  }

  cycleTheme() {
    const next = this.currentTheme() === 'dark' ? 'light' : 'dark';
    this.currentTheme.set(next);
    this.applyTheme(next);
  }

  private applyTheme(theme: 'dark' | 'light') {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }

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
