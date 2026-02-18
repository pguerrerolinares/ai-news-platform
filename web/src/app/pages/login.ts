import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-login',
  imports: [FormsModule],
  template: `
    <div class="login-container">
      <div class="login-card">
        <h1>AI News Platform</h1>
        <p class="subtitle">Ingresa para acceder al panel</p>

        @if (errorMsg()) {
          <div class="error">{{ errorMsg() }}</div>
        }

        <form (ngSubmit)="onLogin()">
          <label for="password">Contrasena</label>
          <input
            id="password"
            type="password"
            [(ngModel)]="password"
            name="password"
            placeholder="Ingresa la contrasena"
            [disabled]="loading()"
            autocomplete="current-password"
          />
          <button type="submit" [disabled]="loading() || !password">
            @if (loading()) {
              Ingresando...
            } @else {
              Ingresar
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
      font-family: system-ui, -apple-system, sans-serif;
      color: #1a1a2e;
      background: #f8fafc;
    }
    .login-container {
      width: 100%;
      max-width: 400px;
      padding: 20px;
    }
    .login-card {
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 32px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
    }
    h1 {
      margin: 0 0 4px;
      font-size: 1.6rem;
      text-align: center;
    }
    .subtitle {
      margin: 0 0 24px;
      color: #64748b;
      font-size: 0.9rem;
      text-align: center;
    }
    .error {
      background: #fef2f2;
      color: #dc2626;
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 0.85rem;
      margin-bottom: 16px;
    }
    label {
      display: block;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 6px;
      color: #475569;
    }
    input {
      width: 100%;
      padding: 10px 12px;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      font-size: 0.95rem;
      margin-bottom: 16px;
      box-sizing: border-box;
      outline: none;
      transition: border-color 0.15s;
    }
    input:focus {
      border-color: #2563eb;
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }
    input:disabled {
      background: #f1f5f9;
    }
    button {
      width: 100%;
      padding: 10px;
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 6px;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
    }
    button:hover:not(:disabled) {
      background: #1d4ed8;
    }
    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
    @media (max-width: 640px) {
      .login-container { padding: 12px; }
      .login-card { padding: 24px; }
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
