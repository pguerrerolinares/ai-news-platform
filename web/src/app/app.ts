import { Component, HostListener, inject, signal } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive, Router } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { AuthService } from './services/auth.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatToolbarModule, MatButtonModule, MatIconModule],
  template: `
    @if (showNav()) {
      <mat-toolbar class="navbar">
        <div class="nav-brand">AI News Platform</div>
        <button mat-icon-button class="hamburger" (click)="toggleMenu()">
          <mat-icon>menu</mat-icon>
        </button>
        <div class="nav-links" [class.open]="menuOpen()">
          <a mat-button routerLink="/dashboard" routerLinkActive="active" (click)="onNavClick()">Dashboard</a>
          <a mat-button routerLink="/archive" routerLinkActive="active" (click)="onNavClick()">Archivo</a>
          <a mat-button routerLink="/search" routerLinkActive="active" (click)="onNavClick()">Buscar</a>
          <a mat-button routerLink="/analytics" routerLinkActive="active" (click)="onNavClick()">Analytics</a>
          <a mat-button routerLink="/chat" routerLinkActive="active" (click)="onNavClick()">Chat</a>
          <button mat-icon-button class="theme-toggle" (click)="cycleTheme()" [title]="'Tema: ' + currentTheme()">
            @if (currentTheme() === 'dark') {
              <mat-icon>dark_mode</mat-icon>
            } @else if (currentTheme() === 'light') {
              <mat-icon>light_mode</mat-icon>
            } @else {
              <mat-icon>monitor</mat-icon>
            }
          </button>
          <button mat-button class="logout-btn" (click)="onLogout()">Salir</button>
        </div>
      </mat-toolbar>
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
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }
    .navbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 28px;
      height: 52px;
      background: color-mix(in srgb, var(--bg-surface) 80%, transparent);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .nav-brand {
      font-family: var(--font-heading);
      font-weight: 800;
      font-size: var(--text-base);
      letter-spacing: var(--tracking-tight);
      color: var(--text-primary);
    }
    .nav-links {
      display: flex;
      align-items: center;
      gap: 2px;
    }
    .nav-links a.mat-mdc-button {
      color: var(--text-muted);
      font-size: var(--text-sm);
      font-weight: 500;
      padding: 6px 14px;
      min-width: auto;
      letter-spacing: var(--tracking-normal);
      position: relative;
      --mdc-text-button-label-text-color: var(--text-muted);
      --mdc-text-button-hover-label-text-color: var(--text-primary);
      transition: color 0.2s ease;
    }
    .nav-links a.mat-mdc-button::after {
      content: '';
      position: absolute;
      bottom: 4px;
      left: 50%;
      transform: translateX(-50%);
      width: 0;
      height: 2px;
      border-radius: 1px;
      background: var(--accent);
      transition: width 0.2s ease;
    }
    .nav-links a.mat-mdc-button:hover {
      color: var(--text-primary);
    }
    .nav-links a.mat-mdc-button:hover::after {
      width: 16px;
    }
    .nav-links a.mat-mdc-button.active {
      color: var(--text-primary);
      font-weight: 600;
      --mdc-text-button-label-text-color: var(--text-primary);
    }
    .nav-links a.mat-mdc-button.active::after {
      width: 20px;
    }
    .theme-toggle {
      color: var(--text-muted);
      margin-left: 4px;
      --mdc-icon-button-icon-color: var(--text-muted);
      transition: color 0.15s ease, transform 0.3s ease;
    }
    .theme-toggle:hover {
      color: var(--text-primary);
      --mdc-icon-button-icon-color: var(--text-primary);
      transform: rotate(15deg);
    }
    .logout-btn {
      color: var(--text-muted);
      font-size: var(--text-sm);
      font-weight: 500;
      margin-left: 4px;
      --mdc-text-button-label-text-color: var(--text-muted);
      --mdc-text-button-hover-label-text-color: var(--text-primary);
    }
    .logout-btn:hover {
      color: var(--text-primary);
    }
    .hamburger {
      display: none;
      color: var(--text-primary);
      --mdc-icon-button-icon-color: var(--text-primary);
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
      .nav-brand { font-size: 0.875rem; }
      .hamburger { display: inline-flex; }
      .nav-links {
        display: flex;
        flex-direction: column;
        position: absolute;
        top: 48px;
        left: 0;
        right: 0;
        background: var(--bg-surface);
        border-bottom: 1px solid var(--border);
        padding: 8px 16px 12px;
        gap: 2px;
        z-index: 99;
        backdrop-filter: blur(12px);
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
      .nav-links a.mat-mdc-button {
        font-size: var(--text-sm);
        padding: 10px 16px;
        width: 100%;
        justify-content: flex-start;
      }
      .nav-links a.mat-mdc-button::after { display: none; }
      .nav-links a.mat-mdc-button.active::after { display: none; }
      .logout-btn { font-size: var(--text-sm); padding: 10px 16px; text-align: left; }
      .theme-toggle { margin: 4px 16px; }
      main.with-nav { padding: 24px 16px; }
    }
  `],
})
export class App {
  private auth = inject(AuthService);
  private router = inject(Router);

  menuOpen = signal(false);
  currentTheme = signal<'dark' | 'light' | 'system'>(this.getInitialTheme());

  private getInitialTheme(): 'dark' | 'light' | 'system' {
    const stored = localStorage.getItem('theme');
    if (stored === 'dark' || stored === 'light') return stored;
    return 'system';
  }

  cycleTheme() {
    const order: ('dark' | 'light' | 'system')[] = ['dark', 'light', 'system'];
    const idx = order.indexOf(this.currentTheme());
    const next = order[(idx + 1) % order.length];
    this.currentTheme.set(next);
    this.applyTheme(next);
  }

  private applyTheme(theme: 'dark' | 'light' | 'system') {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else if (theme === 'light') {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    } else {
      localStorage.removeItem('theme');
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
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
