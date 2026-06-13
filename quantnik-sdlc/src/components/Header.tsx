import { LogOut, Moon, Search, Sun } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Avatar, AvatarFallback } from './ui/avatar';
import { Tooltip, TooltipContent, TooltipTrigger } from './ui/tooltip';
import LogoLightThemePro from '../imports/LogoLightThemePro';
import DarkThemeLogo from './DarkThemeLogo';
import { useAuth } from '../auth/AuthContext';
import { useAbility } from '../auth/abilities';
import { getRoleDisplayName } from '../constants/roleLabels';

interface HeaderProps {
  onLogoClick?: () => void;
  isDarkMode?: boolean;
  onToggleTheme?: () => void;
  onNavigateToEnablement?: () => void;
  onNavigateToDemo?: () => void;
  onNavigateToExecute?: () => void;
  onNavigateToUniversity?: () => void;
  onNavigateToSupport?: () => void;
  onNavigateToAbout?: () => void;
  onNavigateToContact?: () => void;
}

export function Header({ onLogoClick, isDarkMode, onToggleTheme, onNavigateToEnablement, onNavigateToDemo, onNavigateToExecute, onNavigateToUniversity, onNavigateToSupport, onNavigateToAbout, onNavigateToContact }: HeaderProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const ability = useAbility();
  const currentPath = location.pathname;

  const hasAgents = (user?.allowedAgents?.length ?? 0) > 0;

  const navItems = [
    { label: 'Enablement', path: '/enablement', onClick: onNavigateToEnablement },
    { label: 'Demo', path: '/demo', onClick: onNavigateToDemo },
    { label: 'Dashboard', path: '/dashboard', onClick: () => navigate('/dashboard'), hidden: !ability.can('manage_users', 'team') },
    { label: 'Execute', path: '/execute', onClick: onNavigateToExecute, hidden: !hasAgents },
    { label: 'University', path: '/university', onClick: onNavigateToUniversity },
    { label: 'Support', path: '/support', onClick: onNavigateToSupport },
    { label: 'About', path: '/about', onClick: onNavigateToAbout },
    { label: 'Contact', path: '/contact', onClick: onNavigateToContact },
  ];

  return (
    <header className="px-6 py-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center">
          <Button
            variant="ghost"
            className="p-0 hover:bg-transparent cursor-pointer relative"
            onClick={onLogoClick}
          >
            <div className="h-[40px] w-auto">
              {isDarkMode ? <DarkThemeLogo /> : <LogoLightThemePro />}
            </div>
          </Button>
        </div>

        {/* Top Navigation */}
        <nav className="flex items-center space-x-6">
          {navItems.filter(item => !item.hidden).map((item) => {
            const isActive = currentPath === item.path;
            return (
              <Button
                key={item.path}
                variant="ghost"
                className={isActive
                  ? 'text-[#3498B3] font-semibold border-b-2 border-[#3498B3] rounded-none pb-1'
                  : 'text-foreground hover:text-[#3498B3]'
                }
                onClick={item.onClick}
              >
                {item.label}
              </Button>
            );
          })}
        </nav>

        {/* Search */}
        <div className="flex-1 max-w-md mx-8">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
            <Input
              type="text"
              placeholder="Search"
              className="pl-10 bg-input-background text-foreground placeholder:text-muted-foreground h-9 py-1 border border-border"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center space-x-4">
          {/* Theme Toggle */}
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={onToggleTheme}
            className="text-muted-foreground hover:text-foreground"
          >
            {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </Button>

          {isLoading ? null : isAuthenticated && user ? (
            <div className="flex items-center gap-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Avatar className="size-8 cursor-default bg-primary text-primary-foreground">
                    <AvatarFallback className="bg-primary text-xs font-medium text-primary-foreground">
                      {user.displayName
                        .split(' ')
                        .map((part) => part[0])
                        .join('')
                        .toUpperCase()
                        .slice(0, 2)}
                    </AvatarFallback>
                  </Avatar>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-xs">
                  <p className="font-medium">{user.displayName}</p>
                  <p>{user.email}</p>
                  <p>{getRoleDisplayName(user.roles[0]) || 'User'}</p>
                </TooltipContent>
              </Tooltip>
              <Button
                variant="ghost"
                size="icon"
                onClick={async () => {
                  await logout();
                  navigate('/login');
                }}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Sign out"
              >
                <LogOut size={16} />
              </Button>
            </div>
          ) : null}
        </div>
        </div>
      </div>
    </header>
  );
}
