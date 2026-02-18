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
      background: #ffffff;
    }
    .login-container {
      width: 100%;
      max-width: 360px;
      padding: 24px;
    }
    .login-card {
      background: white;
      border-radius: 18px;
      padding: 40px 36px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04), 0 8px 32px rgba(0, 0, 0, 0.08);
    }
    h1 {
      margin: 0 0 6px;
      font-size: 1.75rem;
      font-weight: 700;
      text-align: center;
      letter-spacing: -0.02em;
      color: #1d1d1f;
    }
    .subtitle {
      margin: 0 0 32px;
      color: #86868b;
      font-size: 0.9375rem;
      text-align: center;
      font-weight: 400;
    }
    .error {
      background: #fff2f2;
      color: #d70015;
      padding: 12px 16px;
      border-radius: 10px;
      font-size: 0.875rem;
      margin-bottom: 20px;
      font-weight: 500;
    }
    label {
      display: block;
      font-size: 0.8125rem;
      font-weight: 500;
      margin-bottom: 6px;
      color: #6e6e73;
    }
    input {
      width: 100%;
      padding: 12px 14px;
      border: 1px solid #d2d2d7;
      border-radius: 10px;
      font-size: 1rem;
      margin-bottom: 20px;
      box-sizing: border-box;
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
      color: #1d1d1f;
      background: #ffffff;
    }
    input:focus {
      border-color: #0071e3;
      box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.12);
    }
    input:disabled {
      background: #f5f5f7;
      color: #86868b;
    }
    button {
      width: 100%;
      padding: 13px;
      background: #0071e3;
      color: white;
      border: none;
      border-radius: 980px;
      font-size: 0.9375rem;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.2s, transform 0.1s;
      letter-spacing: -0.01em;
    }
    button:hover:not(:disabled) {
      background: #0077ED;
    }
    button:active:not(:disabled) {
      transform: scale(0.985);
    }
    button:disabled {
      opacity: 0.42;
      cursor: default;
    }
    @media (max-width: 640px) {
      .login-container { padding: 16px; }
      .login-card { padding: 32px 24px; }
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
