import React from 'react';
import './App.css';
import Agent from './components/Agent';
import Login from './components/Login';
// import { MsalAuthProvider } from './auth/components/msal-auth-provider';
// import { AuthProvider } from './auth/context/AuthContext';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
// import { AuthGuard } from './auth/components/auth-guard';
// JWT Authentication (ACTIVE)
import { JWTAuthProvider } from './jwt-auth/contexts/JWTAuthContext';
import { JWTAuthGuard } from './jwt-auth/components/JWTAuthGuard';

function App() {
  
//   // Determine the primary path based on whether URL contains localhost
  const isLocalhost = window.location.href.includes('localhost');
  const primaryPath = isLocalhost ? "/" : "/documentation";
  return (
    // JWT Authentication (ACTIVE)
    <JWTAuthProvider>
      <BrowserRouter>
       <Routes>
         <Route
              path={primaryPath}
              element={
                <JWTAuthGuard>
                  <Agent />
                </JWTAuthGuard>
              }
            />
       </Routes>
      </BrowserRouter>
    </JWTAuthProvider>

    // <MsalAuthProvider>
    //   <AuthProvider>
    //     <BrowserRouter>
    //      <Routes>
    //           <Route path="/" element={<Login />} />
    //           <Route 
    //             path="/documentation" 
    //             element={
    //               <AuthGuard>
    //                 <Agent />
    //               </AuthGuard>
    //             } 
    //           />
    //         </Routes>
    //     </BrowserRouter>
    //   </AuthProvider>
    // </MsalAuthProvider>
  );

}

export default App;