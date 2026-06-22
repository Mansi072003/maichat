import { Bot, Calendar, FileText, Home, Phone, Send, Stethoscope, Truck, User } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './App.css';

const MaiBot = () => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'bot',
      text: "Hi! Welcome to Mai Health! 👋 I'm MaiBot, your AI health assistant powered by advanced AI. I can help you with consultations, lab tests, medicine delivery, and more. How can I assist you today?",
      timestamp: new Date()
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const quickActions = [
    { icon: Stethoscope, text: "Book Consultation", key: "consultation" },
    { icon: Home, text: "Home Sample Collection", key: "sample" },
    { icon: Truck, text: "Medicine Delivery", key: "medicine" },
    { icon: FileText, text: "View Reports", key: "reports" },
    { icon: Calendar, text: "Schedule Appointment", key: "appointment" },
    { icon: Phone, text: "Contact Support", key: "support" }
  ];

  const handleSendMessage = async (messageText = null) => {
    const text = messageText || inputValue.trim();
    if (!text) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      text: text,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsTyping(true);

    try {
      // Call backend API
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: text,
          patient_id: "default_patient", // You might want to make this dynamic later
          session_id: "default"
        })
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const data = await response.json();

      const botResponse = {
        id: Date.now() + 1,
        type: 'bot',
        text: data.answer,
        timestamp: new Date()
      };

      setMessages(prev => [...prev, botResponse]);
    } catch (error) {
      console.error('Error generating response:', error);
      const fallbackResponse = {
        id: Date.now() + 1,
        type: 'bot',
        text: "I apologize, but I'm having trouble connecting to the server. Please try again later.",
        timestamp: new Date()
      };
      setMessages(prev => [...prev, fallbackResponse]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleQuickAction = (action) => {
    const actionMessages = {
      consultation: "I'd like to book a consultation with a doctor",
      sample: "I need home sample collection service",
      medicine: "I want to order medicine delivery",
      reports: "I want to view my medical reports",
      appointment: "I'd like to schedule an appointment",
      support: "I need to contact support"
    };

    handleSendMessage(actionMessages[action]);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      maxWidth: '1000px',
      margin: '0 auto',
      background: 'linear-gradient(135deg, #e3f2fd 0%, #e8eaf6 100%)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif'
    }}>
      {/* Header */}
      <div style={{
        background: 'white',
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
        borderBottom: '4px solid #2196f3'
      }}>
        <div style={{
          padding: '1rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{
              background: '#2196f3',
              padding: '0.5rem',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Bot style={{ width: '1.5rem', height: '1.5rem', color: 'white' }} />
            </div>
            <div>
              <h1 style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#1f2937', margin: 0 }}>
                MaiBot - AI Health Assistant
              </h1>
              <p style={{ fontSize: '0.875rem', color: '#6b7280', margin: 0 }}>
                Powered by Mistral AI & Vector Knowledge Base
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div style={{
        background: 'white',
        borderBottom: '1px solid #e5e7eb',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
        padding: '1rem'
      }}>
        <p style={{ fontSize: '0.875rem', color: '#6b7280', margin: '0 0 0.75rem 0' }}>
          Quick Actions:
        </p>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '0.5rem'
        }}>
          {quickActions.map((action) => (
            <button
              key={action.key}
              onClick={() => handleQuickAction(action.key)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.5rem',
                background: '#e3f2fd',
                border: 'none',
                borderRadius: '0.5rem',
                cursor: 'pointer',
                fontSize: '0.875rem'
              }}
            >
              <action.icon style={{ width: '1rem', height: '1rem', color: '#1976d2' }} />
              <span>{action.text}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '1rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem'
      }}>
        {messages.map((message) => (
          <div
            key={message.id}
            style={{
              display: 'flex',
              width: '100%',
              justifyContent: message.type === 'user' ? 'flex-end' : 'flex-start'
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.5rem',
              maxWidth: '70%'
            }}>
              {message.type === 'bot' && (
                <div style={{
                  padding: '0.5rem',
                  borderRadius: '50%',
                  background: '#2196f3',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  <Bot style={{ width: '1rem', height: '1rem', color: 'white' }} />
                </div>
              )}

              <div style={{
                padding: '0.75rem 1rem',
                borderRadius: '1rem',
                background: message.type === 'user' ? '#2196f3' : 'white',
                color: message.type === 'user' ? 'white' : '#1f2937',
                border: message.type === 'bot' ? '1px solid #e5e7eb' : 'none',
                boxShadow: message.type === 'bot' ? '0 1px 3px rgba(0, 0, 0, 0.1)' : 'none',
                borderBottomRightRadius: message.type === 'user' ? '0.25rem' : '1rem',
                borderBottomLeftRadius: message.type === 'bot' ? '0.25rem' : '1rem'
              }}>
                {message.type === 'bot' ? (
                  <div className="bot-markdown" style={{ fontSize: '0.875rem', lineHeight: 1.6 }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {message.text}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div style={{ fontSize: '0.875rem', lineHeight: 1.5, whiteSpace: 'pre-line' }}>
                    {message.text}
                  </div>
                )}
                <div style={{
                  fontSize: '0.75rem',
                  marginTop: '0.5rem',
                  opacity: 0.7,
                  color: message.type === 'user' ? '#e3f2fd' : '#6b7280'
                }}>
                  {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>

              {message.type === 'user' && (
                <div style={{
                  padding: '0.5rem',
                  borderRadius: '50%',
                  background: '#6b7280',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  <User style={{ width: '1rem', height: '1rem', color: 'white' }} />
                </div>
              )}
            </div>
          </div>
        ))}

        {isTyping && (
          <div style={{ display: 'flex', width: '100%', justifyContent: 'flex-start' }}>
            <div style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.5rem',
              maxWidth: '70%'
            }}>
              <div style={{
                padding: '0.5rem',
                borderRadius: '50%',
                background: '#2196f3',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Bot style={{ width: '1rem', height: '1rem', color: 'white' }} />
              </div>
              <div style={{
                padding: '0.75rem 1rem',
                borderRadius: '1rem',
                background: 'white',
                border: '1px solid #e5e7eb',
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
                borderBottomLeftRadius: '0.25rem'
              }}>
                <div style={{ display: 'flex', gap: '0.25rem', padding: '0.5rem 0' }}>
                  <div style={{
                    width: '0.5rem',
                    height: '0.5rem',
                    background: '#9e9e9e',
                    borderRadius: '50%',
                    animation: 'bounce 1.4s infinite ease-in-out both'
                  }}></div>
                  <div style={{
                    width: '0.5rem',
                    height: '0.5rem',
                    background: '#9e9e9e',
                    borderRadius: '50%',
                    animation: 'bounce 1.4s infinite ease-in-out both',
                    animationDelay: '-0.16s'
                  }}></div>
                  <div style={{
                    width: '0.5rem',
                    height: '0.5rem',
                    background: '#9e9e9e',
                    borderRadius: '50%',
                    animation: 'bounce 1.4s infinite ease-in-out both',
                    animationDelay: '-0.32s'
                  }}></div>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{
        background: 'white',
        borderTop: '1px solid #e5e7eb',
        boxShadow: '0 -4px 6px rgba(0, 0, 0, 0.1)',
        padding: '1rem'
      }}>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end' }}>
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask me about consultations, tests, medicine delivery, or any health service..."
            style={{
              flex: 1,
              border: '1px solid #d1d5db',
              borderRadius: '1rem',
              padding: '0.75rem 1rem',
              resize: 'none',
              fontFamily: 'inherit',
              fontSize: '0.875rem',
              lineHeight: 1.5,
              minHeight: '2.75rem',
              maxHeight: '7.5rem',
              outline: 'none'
            }}
            rows="1"
          />
          <button
            onClick={() => handleSendMessage()}
            disabled={!inputValue.trim()}
            style={{
              background: inputValue.trim() ? '#2196f3' : '#d1d5db',
              color: 'white',
              border: 'none',
              borderRadius: '1rem',
              padding: '0.75rem 1.5rem',
              cursor: inputValue.trim() ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: '2.75rem'
            }}
          >
            <Send style={{ width: '1.25rem', height: '1.25rem' }} />
          </button>
        </div>
        <p style={{
          fontSize: '0.75rem',
          color: '#6b7280',
          textAlign: 'center',
          margin: '0.5rem 0 0 0'
        }}>
          Mai Health MaiBot - Enhanced with AI and Vector Knowledge Base
        </p>
      </div>
    </div>
  );
};

export default MaiBot;