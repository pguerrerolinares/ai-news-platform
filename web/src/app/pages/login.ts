import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-login',
  imports: [FormsModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  template: `
    <div class="login-container">
      <div class="login-card">
        <div class="brand-line"></div>
        <h1>AI NEWS<br/>AGGREGATOR</h1>
        <p class="subtitle mono">INGRESA PARA ACCEDER AL PANEL</p>

        @if (errorMsg()) {
          <div class="error mono">{{ errorMsg() }}</div>
        }

        <form (ngSubmit)="onLogin()">
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Contraseña</mat-label>
            <input
              matInput
              id="password"
              type="password"
              [(ngModel)]="password"
              name="password"
              placeholder="Ingresa la contraseña"
              [disabled]="loading()"
              autocomplete="current-password"
            />
          </mat-form-field>
          <button
            mat-flat-button
            type="submit"
            class="submit-btn full-width"
            [disabled]="loading() || !password"
          >
            @if (loading()) {
              INGRESANDO...
            } @else {
              INGRESAR
            }
          </button>
        </form>
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      background: var(--bg-base);
    }

    .login-container {
      width: 100%;
      max-width: 400px;
      padding: 24px;
    }

    .login-card {
      padding: 52px 44px;
      border: 1px solid var(--text-primary);
      background: var(--bg-surface);
      animation: scale-in 0.5s ease-out both;
    }

    .brand-line {
      width: 40px;
      height: 3px;
      background: var(--accent);
      margin-bottom: 24px;
    }

    h1 {
      margin: 0 0 8px;
      font-family: var(--font-heading);
      font-size: var(--text-2xl);
      font-weight: 700;
      letter-spacing: -0.03em;
      color: var(--text-primary);
      line-height: 0.95;
      text-transform: uppercase;
    }

    .subtitle {
      margin: 0 0 36px;
      color: var(--text-muted);
      font-size: 10px;
      letter-spacing: 0.1em;
    }
    .mono { font-family: var(--font-mono); }

    .error {
      background: var(--error-subtle);
      color: var(--error);
      padding: 12px 16px;
      border: 1px solid rgba(239, 68, 68, 0.15);
      font-size: 11px;
      margin-bottom: 20px;
      letter-spacing: 0.04em;
    }

    .full-width { width: 100%; }

    mat-form-field.full-width { margin-bottom: 8px; }

    button.submit-btn {
      height: 52px;
      font-size: 11px;
      letter-spacing: 0.08em;
    }

    @media (max-width: 640px) {
      .login-container { padding: 16px; }
      .login-card { padding: 40px 28px; }
    }
  `],
})
export class LoginPage {
  private auth = inject(AuthService);
  private router = inject(Router);

  password = '';
  loading = signal(false);
  errorMsg = signal<string | null>(null);

  onLogin() {
    if (!this.password) return;
    this.loading.set(true);
    this.errorMsg.set(null);

    this.auth.login(this.password).subscribe({
      next: () => {
        this.loading.set(false);
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        this.loading.set(false);
        if (err.status === 401 || err.status === 403) {
          this.errorMsg.set('Contraseña incorrecta');
        } else {
          this.errorMsg.set('Error de conexión. Intenta de nuevo.');
        }
      },
    });
  }
}
