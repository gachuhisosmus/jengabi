import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { 
  TrendingUp, 
  FileText, 
  Users, 
  Calendar,
  Zap,
  MessageCircle,
  BarChart3,
  Clock,
  PlayCircle,
  Instagram,
  Facebook,
  Youtube
} from 'lucide-react'

const Dashboard = () => {
  const [stats, setStats] = useState({
    pendingTasks: 0,
    totalContent: 0,
    audienceGrowth: 0,
    engagementRate: 0
  })

  useEffect(() => {
    // Mock data for demonstration
    setStats({
      pendingTasks: 3,
      totalContent: 24,
      audienceGrowth: 15,
      engagementRate: 8.2
    })
  }, [])

  // Professional color scheme
  const colors = {
    primary: '#3B82F6',
    primaryDark: '#1D4ED8',
    secondary: '#10B981',
    accent: '#8B5CF6',
    background: '#F8FAFC',
    card: '#FFFFFF',
    text: '#1F2937',
    textLight: '#6B7280',
    border: '#E5E7EB'
  }

  const styles = {
    container: {
      minHeight: '100vh',
      backgroundColor: colors.background,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    },
    header: {
      backgroundColor: colors.card,
      borderBottom: `1px solid ${colors.border}`,
      boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
    },
    headerContent: {
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '16px 20px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center'
    },
    main: {
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '32px 20px'
    },
    gradientText: {
      background: `linear-gradient(135deg, ${colors.primary}, ${colors.primaryDark})`,
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      backgroundClip: 'text'
    },
    card: {
      backgroundColor: colors.card,
      borderRadius: '12px',
      border: `1px solid ${colors.border}`,
      boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
      overflow: 'hidden'
    },
    statCard: {
      backgroundColor: colors.card,
      borderRadius: '12px',
      border: `1px solid ${colors.border}`,
      padding: '24px',
      transition: 'all 0.2s ease-in-out'
    },
    button: {
      backgroundColor: colors.primary,
      color: 'white',
      border: 'none',
      borderRadius: '8px',
      padding: '12px 24px',
      fontSize: '14px',
      fontWeight: '600',
      cursor: 'pointer',
      textDecoration: 'none',
      display: 'inline-flex',
      alignItems: 'center',
      gap: '8px',
      transition: 'all 0.2s ease-in-out'
    },
    secondaryButton: {
      backgroundColor: colors.card,
      color: colors.text,
      border: `1px solid ${colors.border}`,
      borderRadius: '8px',
      padding: '12px 24px',
      fontSize: '14px',
      fontWeight: '500',
      cursor: 'pointer',
      textDecoration: 'none',
      display: 'inline-flex',
      alignItems: 'center',
      gap: '8px',
      transition: 'all 0.2s ease-in-out'
    }
  }

  const statsCards = [
    {
      name: 'Pending Tasks',
      value: stats.pendingTasks,
      icon: FileText,
      color: colors.primary,
      trend: '+2'
    },
    {
      name: 'Content Created',
      value: stats.totalContent,
      icon: Calendar,
      color: colors.secondary,
      trend: 'This month'
    },
    {
      name: 'Audience Growth',
      value: `${stats.audienceGrowth}%`,
      icon: TrendingUp,
      color: colors.accent,
      trend: '+5%'
    },
    {
      name: 'Engagement Rate',
      value: `${stats.engagementRate}%`,
      icon: Users,
      color: '#F59E0B',
      trend: 'Above avg'
    }
  ]

  const quickActions = [
    {
      name: 'Generate Ideas',
      description: 'AI-powered content ideas',
      icon: Zap,
      color: colors.primary,
      href: '/marketing'
    },
    {
      name: 'Create Content',
      description: 'Plan and schedule posts',
      icon: FileText,
      color: colors.secondary,
      href: '/content'
    },
    {
      name: 'Analyze Performance',
      description: 'View analytics & insights',
      icon: BarChart3,
      color: colors.accent,
      href: '/analytics'
    },
    {
      name: 'Customer Insights',
      description: 'Analyze feedback',
      icon: MessageCircle,
      color: '#EC4899',
      href: '/marketing'
    }
  ]

  const recentTasks = [
    {
      id: 1,
      title: 'Instagram Product Launch',
      platform: 'instagram',
      dueDate: '2024-01-15',
      priority: 'high'
    },
    {
      id: 2,
      title: 'Facebook Customer Stories',
      platform: 'facebook',
      dueDate: '2024-01-16',
      priority: 'medium'
    },
    {
      id: 3,
      title: 'YouTube Tutorial',
      platform: 'youtube',
      dueDate: '2024-01-18',
      priority: 'low'
    }
  ]

  const getPlatformIcon = (platform) => {
    const icons = {
      instagram: Instagram,
      facebook: Facebook,
      youtube: Youtube
    }
    const Icon = icons[platform] || FileText
    return <Icon size={18} />
  }

  const getPriorityColor = (priority) => {
    const colors = {
      high: '#EF4444',
      medium: '#F59E0B',
      low: '#10B981'
    }
    return colors[priority] || colors.low
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.headerContent}>
          <div>
            <h1 style={{...styles.gradientText, fontSize: '24px', fontWeight: 'bold', margin: 0}}>
              Dashboard
            </h1>
            <p style={{color: colors.textLight, margin: '4px 0 0 0', fontSize: '14px'}}>
              Welcome back! Here's your business overview.
            </p>
          </div>
          <div style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
            <div style={{
              width: '8px',
              height: '8px',
              backgroundColor: '#10B981',
              borderRadius: '50%',
              animation: 'pulse 2s infinite'
            }}></div>
            <span style={{fontSize: '14px', color: colors.textLight}}>System Online</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main style={styles.main}>
        {/* Stats Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '20px',
          marginBottom: '32px'
        }}>
          {statsCards.map((stat, index) => {
            const Icon = stat.icon
            return (
              <div 
                key={index}
                style={styles.statCard}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)'
                  e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)'
                  e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)'
                }}
              >
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start'}}>
                  <div>
                    <p style={{color: colors.textLight, fontSize: '14px', fontWeight: '500', margin: '0 0 8px 0'}}>
                      {stat.name}
                    </p>
                    <p style={{color: colors.text, fontSize: '32px', fontWeight: 'bold', margin: '0 0 4px 0'}}>
                      {stat.value}
                    </p>
                    <span style={{
                      color: stat.trend.includes('+') ? '#10B981' : colors.textLight,
                      fontSize: '12px',
                      fontWeight: '500'
                    }}>
                      {stat.trend}
                    </span>
                  </div>
                  <div style={{
                    backgroundColor: `${stat.color}20`,
                    borderRadius: '10px',
                    padding: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    <Icon size={24} color={stat.color} />
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '32px',
          marginBottom: '32px'
        }}>
          {/* Pending Tasks */}
          <div style={styles.card}>
            <div style={{padding: '24px'}}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px'}}>
                <h2 style={{color: colors.text, fontSize: '18px', fontWeight: '600', margin: 0}}>
                  Pending Tasks
                </h2>
                <Link 
                  to="/content" 
                  style={{
                    color: colors.primary,
                    fontSize: '14px',
                    fontWeight: '500',
                    textDecoration: 'none'
                  }}
                >
                  View all →
                </Link>
              </div>
              
              <div style={{display: 'flex', flexDirection: 'column', gap: '12px'}}>
                {recentTasks.map((task) => (
                  <div 
                    key={task.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '16px',
                      backgroundColor: `${colors.background}`,
                      borderRadius: '8px',
                      border: `1px solid ${colors.border}`,
                      transition: 'all 0.2s ease-in-out'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = '#F1F5F9'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = colors.background
                    }}
                  >
                    <div style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: '40px',
                        height: '40px',
                        backgroundColor: 'white',
                        borderRadius: '8px',
                        border: `1px solid ${colors.border}`
                      }}>
                        {getPlatformIcon(task.platform)}
                      </div>
                      <div>
                        <p style={{color: colors.text, fontSize: '14px', fontWeight: '500', margin: '0 0 4px 0'}}>
                          {task.title}
                        </p>
                        <p style={{color: colors.textLight, fontSize: '12px', margin: 0}}>
                          Due {new Date(task.dueDate).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <span style={{
                      backgroundColor: `${getPriorityColor(task.priority)}20`,
                      color: getPriorityColor(task.priority),
                      padding: '4px 12px',
                      borderRadius: '20px',
                      fontSize: '12px',
                      fontWeight: '500',
                      textTransform: 'capitalize'
                    }}>
                      {task.priority}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div style={styles.card}>
            <div style={{padding: '24px'}}>
              <h2 style={{color: colors.text, fontSize: '18px', fontWeight: '600', margin: '0 0 20px 0'}}>
                Quick Actions
              </h2>
              
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '16px'
              }}>
                {quickActions.map((action, index) => {
                  const Icon = action.icon
                  return (
                    <Link
                      key={index}
                      to={action.href}
                      style={{
                        ...styles.secondaryButton,
                        flexDirection: 'column',
                        alignItems: 'flex-start',
                        padding: '20px',
                        gap: '12px',
                        textAlign: 'left'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#F8FAFC'
                        e.currentTarget.style.borderColor = action.color
                        e.currentTarget.style.transform = 'translateY(-2px)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = colors.card
                        e.currentTarget.style.borderColor = colors.border
                        e.currentTarget.style.transform = 'translateY(0)'
                      }}
                    >
                      <div style={{
                        backgroundColor: `${action.color}20`,
                        borderRadius: '8px',
                        padding: '8px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}>
                        <Icon size={20} color={action.color} />
                      </div>
                      <div>
                        <h3 style={{color: colors.text, fontSize: '14px', fontWeight: '600', margin: '0 0 4px 0'}}>
                          {action.name}
                        </h3>
                        <p style={{color: colors.textLight, fontSize: '12px', margin: 0}}>
                          {action.description}
                        </p>
                      </div>
                    </Link>
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        {/* AI Recommendations */}
        <div style={styles.card}>
          <div style={{padding: '24px'}}>
            <div style={{display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px'}}>
              <Zap size={20} color="#F59E0B" />
              <h2 style={{color: colors.text, fontSize: '18px', fontWeight: '600', margin: 0}}>
                AI Recommendations
              </h2>
            </div>
            
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
              gap: '16px'
            }}>
              <div style={{
                padding: '16px',
                backgroundColor: `${colors.primary}10`,
                borderRadius: '8px',
                border: `1px solid ${colors.primary}30`
              }}>
                <div style={{display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px'}}>
                  <TrendingUp size={16} color={colors.primary} />
                  <span style={{color: colors.text, fontSize: '14px', fontWeight: '500'}}>
                    Trending Hashtag
                  </span>
                </div>
                <p style={{color: colors.text, fontSize: '14px', margin: '0 0 8px 0'}}>
                  #AfricanCreators is trending with 15K+ posts this week
                </p>
                <span style={{
                  color: '#10B981',
                  fontSize: '12px',
                  fontWeight: '500'
                }}>
                  High engagement potential
                </span>
              </div>

              <div style={{
                padding: '16px',
                backgroundColor: `${colors.secondary}10`,
                borderRadius: '8px',
                border: `1px solid ${colors.secondary}30`
              }}>
                <div style={{display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px'}}>
                  <PlayCircle size={16} color={colors.secondary} />
                  <span style={{color: colors.text, fontSize: '14px', fontWeight: '500'}}>
                    Content Idea
                  </span>
                </div>
                <p style={{color: colors.text, fontSize: '14px', margin: '0 0 8px 0'}}>
                  Behind-the-scenes manufacturing process videos
                </p>
                <span style={{
                  color: '#F59E0B',
                  fontSize: '12px',
                  fontWeight: '500'
                }}>
                  Medium engagement
                </span>
              </div>

              <div style={{
                padding: '16px',
                backgroundColor: `${colors.accent}10`,
                borderRadius: '8px',
                border: `1px solid ${colors.accent}30`
              }}>
                <div style={{display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px'}}>
                  <Clock size={16} color={colors.accent} />
                  <span style={{color: colors.text, fontSize: '14px', fontWeight: '500'}}>
                    Best Time to Post
                  </span>
                </div>
                <p style={{color: colors.text, fontSize: '14px', margin: '0 0 8px 0'}}>
                  Post at 7-9 PM for maximum audience reach
                </p>
                <span style={{
                  color: '#10B981',
                  fontSize: '12px',
                  fontWeight: '500'
                }}>
                  High engagement potential
                </span>
              </div>
            </div>
          </div>
        </div>
      </main>

      <style>
        {`
          @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
          }
        `}
      </style>
    </div>
  )
}

export default Dashboard