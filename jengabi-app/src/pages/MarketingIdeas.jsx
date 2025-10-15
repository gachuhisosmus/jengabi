import React, { useState } from 'react'
import { useSupabase } from '../contexts/SupabaseContext'
import { 
  Zap, 
  Copy, 
  Sparkles, 
  Instagram, 
  Facebook, 
  Twitter,
  CheckCircle,
  Clock,
  TrendingUp
} from 'lucide-react'

const MarketingIdeas = () => {
  const { user } = useSupabase()
  const [selectedProducts, setSelectedProducts] = useState([])
  const [selectedPlatform, setSelectedPlatform] = useState('instagram')
  const [ideas, setIdeas] = useState([])
  const [isGenerating, setIsGenerating] = useState(false)
  const [copiedIndex, setCopiedIndex] = useState(null)

  // Mock user products - will come from database
  const userProducts = [
    'African Print Dresses',
    'Handmade Jewelry', 
    'Artisan Bags',
    'Traditional Accessories'
  ]

  const platforms = [
    { id: 'instagram', name: 'Instagram', icon: Instagram, color: '#E4405F' },
    { id: 'facebook', name: 'Facebook', icon: Facebook, color: '#1877F2' },
    { id: 'tiktok', name: 'TikTok', icon: Clock, color: '#000000' },
    { id: 'twitter', name: 'Twitter', icon: Twitter, color: '#1DA1F2' }
  ]

  const styles = {
    container: {
      minHeight: '100vh',
      backgroundColor: '#F8FAFC',
      padding: '24px'
    },
    card: {
      backgroundColor: 'white',
      borderRadius: '12px',
      border: '1px solid #E5E7EB',
      boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
      overflow: 'hidden'
    },
    button: {
      primary: {
        backgroundColor: '#3B82F6',
        color: 'white',
        border: 'none',
        borderRadius: '8px',
        padding: '12px 24px',
        fontSize: '14px',
        fontWeight: '600',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        transition: 'all 0.2s ease-in-out'
      },
      secondary: {
        backgroundColor: 'white',
        color: '#374151',
        border: '1px solid #D1D5DB',
        borderRadius: '8px',
        padding: '8px 16px',
        fontSize: '14px',
        fontWeight: '500',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        transition: 'all 0.2s ease-in-out'
      }
    }
  }

  const handleProductToggle = (product) => {
    if (selectedProducts.includes(product)) {
      setSelectedProducts(selectedProducts.filter(p => p !== product))
    } else {
      setSelectedProducts([...selectedProducts, product])
    }
  }

  const generateIdeas = async () => {
    if (selectedProducts.length === 0) return
    
    setIsGenerating(true)
    
    // Simulate API call to your existing bot
    setTimeout(() => {
      const mockIdeas = [
        {
          id: 1,
          content: `🌟 New ${selectedProducts[0]} just dropped! ✨ Who's copping first? 👀\n\n#AfricanFashion #SupportLocal #MadeInAfrica #NewArrivals`,
          platform: selectedPlatform,
          type: 'post',
          engagement: 'high'
        },
        {
          id: 2,
          content: `Behind the scenes! 👀 Watch how we create our beautiful ${selectedProducts[0]} from start to finish. Which step surprises you most? 💫\n\n#BehindTheScenes #AfricanCreators #ArtisanMade #Handcrafted`,
          platform: selectedPlatform,
          type: 'reel',
          engagement: 'medium'
        },
        {
          id: 3,
          content: `Customer love! ❤️ Jane rocked our ${selectedProducts[0]} at her sister's wedding. Tag someone who needs this stunning piece! 👇\n\n#CustomerSpotlight #AfricanStyle #WeddingFashion #SupportSmallBusiness`,
          platform: selectedPlatform,
          type: 'story',
          engagement: 'high'
        }
      ]
      setIdeas(mockIdeas)
      setIsGenerating(false)
    }, 2000)
  }

  const copyToClipboard = async (text, index) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedIndex(index)
      setTimeout(() => setCopiedIndex(null), 2000)
    } catch (err) {
      console.error('Failed to copy text: ', err)
    }
  }

  const getEngagementColor = (engagement) => {
    const colors = {
      high: '#10B981',
      medium: '#F59E0B',
      low: '#6B7280'
    }
    return colors[engagement] || colors.medium
  }

  return (
    <div style={styles.container}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: '32px' }}>
          <h1 style={{ 
            fontSize: '28px', 
            fontWeight: 'bold', 
            color: '#1F2937',
            margin: '0 0 8px 0'
          }}>
            Marketing Ideas
          </h1>
          <p style={{ 
            fontSize: '16px', 
            color: '#6B7280',
            margin: 0
          }}>
            AI-powered content ideas tailored for your African business
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '32px' }}>
          {/* Sidebar - Configuration */}
          <div style={styles.card}>
            <div style={{ padding: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
                <div style={{
                  padding: '8px',
                  borderRadius: '8px',
                  backgroundColor: '#3B82F620'
                }}>
                  <Zap size={20} color="#3B82F6" />
                </div>
                <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1F2937', margin: 0 }}>
                  Generate Ideas
                </h2>
              </div>

              {/* Product Selection */}
              <div style={{ marginBottom: '24px' }}>
                <label style={{ 
                  display: 'block', 
                  fontSize: '14px', 
                  fontWeight: '500', 
                  color: '#374151',
                  marginBottom: '12px'
                }}>
                  Select Products to Promote
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {userProducts.map((product, index) => (
                    <button
                      key={index}
                      onClick={() => handleProductToggle(product)}
                      style={{
                        ...styles.button.secondary,
                        backgroundColor: selectedProducts.includes(product) ? '#3B82F620' : 'white',
                        borderColor: selectedProducts.includes(product) ? '#3B82F6' : '#D1D5DB',
                        color: selectedProducts.includes(product) ? '#3B82F6' : '#374151',
                        justifyContent: 'flex-start'
                      }}
                    >
                      {selectedProducts.includes(product) ? (
                        <CheckCircle size={16} />
                      ) : (
                        <div style={{ width: '16px', height: '16px', border: '2px solid #9CA3AF', borderRadius: '4px' }} />
                      )}
                      {product}
                    </button>
                  ))}
                </div>
              </div>

              {/* Platform Selection */}
              <div style={{ marginBottom: '24px' }}>
                <label style={{ 
                  display: 'block', 
                  fontSize: '14px', 
                  fontWeight: '500', 
                  color: '#374151',
                  marginBottom: '12px'
                }}>
                  Choose Platform
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  {platforms.map((platform) => {
                    const Icon = platform.icon
                    return (
                      <button
                        key={platform.id}
                        onClick={() => setSelectedPlatform(platform.id)}
                        style={{
                          ...styles.button.secondary,
                          backgroundColor: selectedPlatform === platform.id ? `${platform.color}20` : 'white',
                          borderColor: selectedPlatform === platform.id ? platform.color : '#D1D5DB',
                          color: selectedPlatform === platform.id ? platform.color : '#374151',
                          flexDirection: 'column',
                          height: '64px',
                          padding: '12px 8px'
                        }}
                      >
                        <Icon size={20} />
                        <span style={{ fontSize: '12px', marginTop: '4px' }}>{platform.name}</span>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Generate Button */}
              <button
                onClick={generateIdeas}
                disabled={selectedProducts.length === 0 || isGenerating}
                style={{
                  ...styles.button.primary,
                  width: '100%',
                  opacity: selectedProducts.length === 0 ? 0.5 : 1,
                  cursor: selectedProducts.length === 0 ? 'not-allowed' : 'pointer'
                }}
                onMouseEnter={(e) => {
                  if (selectedProducts.length > 0) {
                    e.target.style.transform = 'translateY(-1px)'
                    e.target.style.boxShadow = '0 4px 12px rgba(59, 130, 246, 0.3)'
                  }
                }}
                onMouseLeave={(e) => {
                  e.target.style.transform = 'translateY(0)'
                  e.target.style.boxShadow = 'none'
                }}
              >
                {isGenerating ? (
                  <>
                    <div style={{ 
                      width: '16px', 
                      height: '16px', 
                      border: '2px solid transparent',
                      borderTop: '2px solid white',
                      borderRadius: '50%',
                      animation: 'spin 1s linear infinite'
                    }} />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    Generate Ideas
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Main Content - Generated Ideas */}
          <div>
            {ideas.length === 0 ? (
              /* Empty State */
              <div style={{
                ...styles.card,
                padding: '48px 24px',
                textAlign: 'center',
                backgroundColor: '#F8FAFC'
              }}>
                <div style={{
                  width: '80px',
                  height: '80px',
                  backgroundColor: '#3B82F620',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 24px'
                }}>
                  <Zap size={32} color="#3B82F6" />
                </div>
                <h3 style={{ 
                  fontSize: '20px', 
                  fontWeight: '600', 
                  color: '#1F2937',
                  margin: '0 0 8px 0'
                }}>
                  No Ideas Generated Yet
                </h3>
                <p style={{ 
                  fontSize: '14px', 
                  color: '#6B7280',
                  margin: '0 0 24px 0',
                  maxWidth: '400px',
                  marginLeft: 'auto',
                  marginRight: 'auto'
                }}>
                  Select your products and platform above to generate AI-powered marketing ideas tailored for your African business.
                </p>
              </div>
            ) : (
              /* Ideas List */
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {ideas.map((idea, index) => {
                  const PlatformIcon = platforms.find(p => p.id === idea.platform)?.icon || Instagram
                  return (
                    <div key={idea.id} style={styles.card}>
                      <div style={{ padding: '24px' }}>
                        {/* Idea Header */}
                        <div style={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          justifyContent: 'space-between',
                          marginBottom: '16px'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <PlatformIcon size={20} color="#6B7280" />
                            <span style={{ 
                              fontSize: '14px', 
                              fontWeight: '500', 
                              color: '#374151',
                              textTransform: 'capitalize'
                            }}>
                              {idea.platform} {idea.type}
                            </span>
                            <div style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '4px 8px',
                              backgroundColor: `${getEngagementColor(idea.engagement)}20`,
                              borderRadius: '12px'
                            }}>
                              <TrendingUp size={12} color={getEngagementColor(idea.engagement)} />
                              <span style={{ 
                                fontSize: '12px', 
                                fontWeight: '500',
                                color: getEngagementColor(idea.engagement),
                                textTransform: 'capitalize'
                              }}>
                                {idea.engagement} engagement
                              </span>
                            </div>
                          </div>
                          
                          <button
                            onClick={() => copyToClipboard(idea.content, index)}
                            style={{
                              ...styles.button.secondary,
                              padding: '8px 12px',
                              backgroundColor: copiedIndex === index ? '#10B981' : 'white',
                              borderColor: copiedIndex === index ? '#10B981' : '#D1D5DB',
                              color: copiedIndex === index ? 'white' : '#374151'
                            }}
                          >
                            {copiedIndex === index ? (
                              <CheckCircle size={14} />
                            ) : (
                              <Copy size={14} />
                            )}
                            {copiedIndex === index ? 'Copied!' : 'Copy'}
                          </button>
                        </div>

                        {/* Idea Content */}
                        <div style={{
                          backgroundColor: '#F8FAFC',
                          padding: '16px',
                          borderRadius: '8px',
                          border: '1px solid #E5E7EB',
                          whiteSpace: 'pre-line',
                          fontSize: '14px',
                          lineHeight: '1.5',
                          color: '#374151'
                        }}>
                          {idea.content}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      <style>
        {`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}
      </style>
    </div>
  )
}

export default MarketingIdeas