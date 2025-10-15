import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { 
  Home, 
  Lightbulb, 
  FileText, 
  BarChart3, 
  User,
  Menu,
  X,
  Zap,
  Settings,
  LogOut,
  Search,
  Bell,
  ChevronDown
} from 'lucide-react'

const Layout = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()

  const navigation = [
    { name: 'Dashboard', href: '/', icon: Home, description: 'Business overview' },
    { name: 'Marketing Ideas', href: '/marketing', icon: Lightbulb, description: 'AI content generation' },
    { name: 'Content Manager', href: '/content', icon: FileText, description: 'Plan & schedule posts' },
    { name: 'Analytics', href: '/analytics', icon: BarChart3, description: 'Performance insights' },
    { name: 'Profile', href: '/profile', icon: User, description: 'Business settings' },
  ]

  // Professional color scheme
  const colors = {
    primary: '#3B82F6',
    primaryDark: '#1D4ED8',
    background: '#F8FAFC',
    card: '#FFFFFF',
    text: '#1F2937',
    textLight: '#6B7280',
    border: '#E5E7EB',
    success: '#10B981'
  }

  const styles = {
    sidebar: {
      backgroundColor: colors.card,
      borderRight: `1px solid ${colors.border}`,
      boxShadow: '2px 0 8px rgba(0,0,0,0.04)'
    },
    logo: {
      background: `linear-gradient(135deg, ${colors.primary}, ${colors.primaryDark})`,
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      backgroundClip: 'text'
    },
    navItem: {
      base: {
        display: 'flex',
        alignItems: 'center',
        padding: '12px 16px',
        borderRadius: '8px',
        textDecoration: 'none',
        transition: 'all 0.2s ease-in-out',
        marginBottom: '4px'
      },
      active: {
        backgroundColor: `${colors.primary}10`,
        color: colors.primary,
        borderLeft: `3px solid ${colors.primary}`
      },
      inactive: {
        color: colors.textLight,
        backgroundColor: 'transparent'
      }
    }
  }

  // Mock user data
  const user = {
    name: 'Sarah Business',
    email: 'sarah@business.com',
    avatar: 'SB',
    plan: 'Pro'
  }

  return (
    <div style={{ 
      display: 'flex', 
      height: '100vh', 
      backgroundColor: colors.background,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      
      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          zIndex: 40,
          display: 'flex'
        }}>
          {/* Mobile Sidebar */}
          <div style={{
            position: 'relative',
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            maxWidth: '320px',
            width: '100%',
            backgroundColor: colors.card
          }}>
            {/* Mobile Header */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '16px',
              borderBottom: `1px solid ${colors.border}`
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  background: `linear-gradient(135deg, ${colors.primary}, ${colors.primaryDark})`,
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <Zap size={18} color="white" />
                </div>
                <div>
                  <h1 style={{ ...styles.logo, fontSize: '20px', fontWeight: 'bold', margin: 0 }}>
                    JengaBI
                  </h1>
                  <p style={{ fontSize: '12px', color: colors.textLight, margin: 0 }}>
                    Creator Platform
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSidebarOpen(false)}
                style={{
                  padding: '8px',
                  borderRadius: '6px',
                  border: 'none',
                  backgroundColor: 'transparent',
                  cursor: 'pointer',
                  color: colors.textLight
                }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Mobile Navigation */}
            <nav style={{ flex: 1, padding: '16px', paddingTop: '24px' }}>
              {navigation.map((item) => {
                const Icon = item.icon
                const isActive = location.pathname === item.href
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    style={{
                      ...styles.navItem.base,
                      ...(isActive ? styles.navItem.active : styles.navItem.inactive)
                    }}
                    onClick={() => setSidebarOpen(false)}
                  >
                    <Icon size={20} style={{ marginRight: '12px' }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '14px', fontWeight: '500' }}>
                        {item.name}
                      </div>
                      <div style={{ fontSize: '12px', color: isActive ? colors.primary : colors.textLight }}>
                        {item.description}
                      </div>
                    </div>
                    {isActive && (
                      <div style={{
                        width: '6px',
                        height: '6px',
                        backgroundColor: colors.primary,
                        borderRadius: '50%'
                      }} />
                    )}
                  </Link>
                )
              })}
            </nav>
          </div>
          
          {/* Click outside to close */}
          <div 
            style={{ flex: 1 }}
            onClick={() => setSidebarOpen(false)}
          />
        </div>
      )}

      {/* Desktop Sidebar */}
      <aside style={{
        ...styles.sidebar,
        display: 'none',
        width: '280px',
        flexDirection: 'column',
        '@media (min-width: 1024px)': {
          display: 'flex'
        }
      }}>
        {/* Logo Section */}
        <div style={{ 
          padding: '24px 20px', 
          borderBottom: `1px solid ${colors.border}`,
          background: 'linear-gradient(135deg, #f8fafc, #f1f5f9)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              background: `linear-gradient(135deg, ${colors.primary}, ${colors.primaryDark})`,
              borderRadius: '10px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)'
            }}>
              <Zap size={22} color="white" />
            </div>
            <div>
              <h1 style={{ ...styles.logo, fontSize: '24px', fontWeight: 'bold', margin: 0 }}>
                JengaBI
              </h1>
              <p style={{ fontSize: '12px', color: colors.textLight, margin: '2px 0 0 0' }}>
                Creator Platform
              </p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: '20px 16px', paddingTop: '24px' }}>
          {navigation.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                style={{
                  ...styles.navItem.base,
                  ...(isActive ? styles.navItem.active : styles.navItem.inactive),
                  borderLeft: isActive ? `3px solid ${colors.primary}` : '3px solid transparent'
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.backgroundColor = '#F8FAFC'
                    e.currentTarget.style.color = colors.text
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.backgroundColor = 'transparent'
                    e.currentTarget.style.color = colors.textLight
                  }
                }}
              >
                <Icon size={20} style={{ marginRight: '12px' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '14px', fontWeight: '500' }}>
                    {item.name}
                  </div>
                  <div style={{ 
                    fontSize: '12px', 
                    color: isActive ? colors.primary : colors.textLight,
                    opacity: isActive ? 1 : 0.7
                  }}>
                    {item.description}
                  </div>
                </div>
              </Link>
            )
          })}
        </nav>

        {/* User Section */}
        <div style={{ 
          padding: '20px 16px', 
          borderTop: `1px solid ${colors.border}`,
          backgroundColor: '#F8FAFC'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px',
            borderRadius: '8px',
            backgroundColor: 'white',
            border: `1px solid ${colors.border}`,
            cursor: 'pointer',
            transition: 'all 0.2s ease-in-out'
          }}
          onClick={() => setUserMenuOpen(!userMenuOpen)}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = colors.primary
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = colors.border
          }}
          >
            <div style={{
              width: '36px',
              height: '36px',
              background: `linear-gradient(135deg, ${colors.primary}, ${colors.primaryDark})`,
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontSize: '14px',
              fontWeight: '600'
            }}>
              {user.avatar}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '14px', fontWeight: '600', color: colors.text }}>
                {user.name}
              </div>
              <div style={{ fontSize: '12px', color: colors.textLight }}>
                {user.plan} Plan
              </div>
            </div>
            <ChevronDown size={16} color={colors.textLight} />
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main style={{ 
        flex: 1, 
        display: 'flex', 
        flexDirection: 'column',
        overflow: 'hidden'
      }}>
        {/* Top Header */}
        <header style={{
          backgroundColor: colors.card,
          borderBottom: `1px solid ${colors.border}`,
          padding: '16px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
        }}>
          {/* Left Section - Menu Button & Search */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            <button
              onClick={() => setSidebarOpen(true)}
              style={{
                padding: '8px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: 'transparent',
                cursor: 'pointer',
                color: colors.text,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#F3F4F6'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent'
              }}
            >
              <Menu size={20} />
            </button>

            {/* Search Bar */}
            <div style={{
              position: 'relative',
              display: 'none',
              alignItems: 'center',
              '@media (min-width: 768px)': {
                display: 'flex'
              }
            }}>
              <Search size={18} style={{ 
                position: 'absolute', 
                left: '12px', 
                color: colors.textLight 
              }} />
              <input
                type="text"
                placeholder="Search..."
                style={{
                  padding: '10px 12px 10px 40px',
                  border: `1px solid ${colors.border}`,
                  borderRadius: '8px',
                  fontSize: '14px',
                  width: '280px',
                  backgroundColor: colors.background,
                  outline: 'none',
                  transition: 'all 0.2s ease-in-out'
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = colors.primary
                  e.target.style.boxShadow = `0 0 0 3px ${colors.primary}20`
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = colors.border
                  e.target.style.boxShadow = 'none'
                }}
              />
            </div>
          </div>

          {/* Right Section - Notifications & User */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {/* Notifications */}
            <button style={{
              padding: '8px',
              borderRadius: '6px',
              border: 'none',
              backgroundColor: 'transparent',
              cursor: 'pointer',
              color: colors.text,
              position: 'relative'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#F3F4F6'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent'
            }}
            >
              <Bell size={20} />
              <div style={{
                position: 'absolute',
                top: '4px',
                right: '4px',
                width: '6px',
                height: '6px',
                backgroundColor: colors.success,
                borderRadius: '50%'
              }} />
            </button>

            {/* User Info (Mobile) */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              '@media (min-width: 1024px)': {
                display: 'none'
              }
            }}>
              <div style={{
                width: '32px',
                height: '32px',
                background: `linear-gradient(135deg, ${colors.primary}, ${colors.primaryDark})`,
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                fontSize: '12px',
                fontWeight: '600'
              }}>
                {user.avatar}
              </div>
            </div>

            {/* User Info (Desktop) */}
            <div style={{
              display: 'none',
              alignItems: 'center',
              gap: '12px',
              padding: '8px 12px',
              borderRadius: '8px',
              cursor: 'pointer',
              transition: 'all 0.2s ease-in-out',
              '@media (min-width: 1024px)': {
                display: 'flex'
              }
            }}
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#F3F4F6'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent'
            }}
            >
              <div style={{
                width: '36px',
                height: '36px',
                background: `linear-gradient(135deg, ${colors.primary}, ${colors.primaryDark})`,
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                fontSize: '14px',
                fontWeight: '600'
              }}>
                {user.avatar}
              </div>
              <div>
                <div style={{ fontSize: '14px', fontWeight: '600', color: colors.text }}>
                  {user.name}
                </div>
                <div style={{ fontSize: '12px', color: colors.textLight }}>
                  {user.plan} Plan
                </div>
              </div>
              <ChevronDown size={16} color={colors.textLight} />
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div style={{ 
          flex: 1, 
          overflow: 'auto',
          padding: '0'
        }}>
          {children}
        </div>
      </main>

      {/* User Menu Dropdown */}
      {userMenuOpen && (
        <div style={{
          position: 'fixed',
          top: '80px',
          right: '24px',
          backgroundColor: colors.card,
          border: `1px solid ${colors.border}`,
          borderRadius: '8px',
          boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
          zIndex: 50,
          minWidth: '200px'
        }}>
          <div style={{ padding: '8px' }}>
            <button style={{
              width: '100%',
              padding: '12px',
              borderRadius: '6px',
              border: 'none',
              backgroundColor: 'transparent',
              cursor: 'pointer',
              color: colors.text,
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              fontSize: '14px',
              transition: 'all 0.2s ease-in-out'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#F3F4F6'
            }}
            >
              <Settings size={16} />
              Settings
            </button>
            <button style={{
              width: '100%',
              padding: '12px',
              borderRadius: '6px',
              border: 'none',
              backgroundColor: 'transparent',
              cursor: 'pointer',
              color: '#EF4444',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              fontSize: '14px',
              transition: 'all 0.2s ease-in-out'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#FEF2F2'
            }}
            >
              <LogOut size={16} />
              Sign Out
            </button>
          </div>
        </div>
      )}

      {/* Close dropdown when clicking outside */}
      {userMenuOpen && (
        <div 
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 40
          }}
          onClick={() => setUserMenuOpen(false)}
        />
      )}
    </div>
  )
}

export default Layout