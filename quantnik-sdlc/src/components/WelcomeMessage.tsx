import { Sun, Moon } from 'lucide-react';
import { USER_NAME } from '../constants/user';

interface WelcomeMessageProps {
  isDarkMode?: boolean;
}

export function WelcomeMessage({ isDarkMode }: WelcomeMessageProps) {
  const getCurrentGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return { text: "Good Morning", icon: Sun };
    if (hour < 17) return { text: "Good Afternoon", icon: Sun };
    return { text: "Good Evening", icon: Moon };
  };

  const { text, icon: GreetingIcon } = getCurrentGreeting();
  const userName = USER_NAME;

  return (
    <div className="px-6 py-6 bg-gradient-to-r from-slate-50 via-blue-50 to-indigo-50 dark:from-gray-800 dark:via-gray-700 dark:to-gray-800 border-b border-gray-100 dark:border-gray-700">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center space-x-4">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 dark:from-blue-600 dark:to-indigo-700 rounded-lg flex items-center justify-center shadow-sm">
            <GreetingIcon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-foreground">
              {text}, {userName}!
            </h1>
            <p className="text-muted-foreground mt-0.5">
              Welcome back to your Wipro QUANTNIK dashboard - Enterprise Software Engineering Platform infused by AI
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}