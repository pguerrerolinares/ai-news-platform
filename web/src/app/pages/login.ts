import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-login',
  imports: [FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  template: `
    <div class="login-container">
      <mat-card class="login-card">
        <h1>AI News Platform</h1>
        <p class="subtitle">Ingresa para acceder al panel</p>

        @if (errorMsg()) {
          <div class="error">{{ errorMsg() }}</div>
        }

        <form (ngSubmit)="onLogin()">
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Contrasena</mat-label>
            <input
              matInput
              id="password"
              type="password"
              [(ngModel)]="password"
              name="password"
              placeholder="Ingresa la contrasena"
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
              Ingresando...
            } @else {
              Ingresar
            }
          </button>
        </form>
      </mat-card>
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
      max-width: 380px;
      padding: 24px;
    }
    .login-card {
      padding: 48px 40px;
    }
    h1 {
      margin: 0 0 6px;
      font-family: var(--font-heading);
      font-size: 2rem;
      font-weight: 700;
      text-align: center;
      letter-spacing: -0.02em;
      color: var(--text-primary);
    }
    .subtitle {
      margin: 0 0 32px;
      color: var(--text-tertiary);
      font-size: 0.9375rem;
      text-align: center;
      font-weight: 400;
    }
    .error {
      background: var(--error-subtle);
      color: #f87171;
      padding: 12px 16px;
      border-radius: 10px;
      border: 1px solid rgba(239,68,68,0.15);
      font-size: 0.875rem;
      margin-bottom: 20px;
      font-weight: 500;
    }
    .full-width {
      width: 100%;
    }
    mat-form-field.full-width {
      margin-bottom: 4px;
    }
    button.submit-btn {
      height: 48px;
      font-size: 0.9375rem;
      font-weight: 600;
      letter-spacing: -0.01em;
      font-family: var(--font-body);
      border-radius: 8px;
    }
    button.submit-btn:active:not(:disabled) {
      transform: scale(0.985);
    }
    @media (max-width: 640px) {
      .login-container { padding: 16px; }
      .login-card { padding: 36px 24px; }
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
          this.errorMsg.set('Contrasena incorrecta');
        } else {
          this.errorMsg.set('Error de conexion. Intenta de nuevo.');
        }
      },
    });
  }
}
