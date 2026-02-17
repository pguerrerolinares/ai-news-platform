import { Routes } from '@angular/router';
import { authGuard } from './guards/auth.guard';
import { LoginPage } from './pages/login';
import { DashboardPage } from './pages/dashboard';
import { ArchivePage } from './pages/archive';
import { SearchPage } from './pages/search';
import { AnalyticsPage } from './pages/analytics';

export const routes: Routes = [
  { path: 'login', component: LoginPage },
  { path: 'dashboard', component: DashboardPage, canActivate: [authGuard] },
  { path: 'archive', component: ArchivePage, canActivate: [authGuard] },
  { path: 'search', component: SearchPage, canActivate: [authGuard] },
  { path: 'analytics', component: AnalyticsPage, canActivate: [authGuard] },
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: '**', redirectTo: 'dashboard' },
];
