import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Phone, Calendar, Truck, FileText, Stethoscope, Home, Settings, Save } from 'lucide-react';

const App = () => {
  // We'll use a new state variable for the patient ID, since the backend now handles everything
  const [patientId, setPatientId] = useState('patient-101');
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'bot',
      text: "Hi! Welcome to Mai Health! 👋 I'm MaiChat, your AI health assistant powered by advanced AI. I can help you with consultations, lab tests, medicine delivery, and more. How can I assist you today?",
      timestamp: new Date()
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
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

  // This is the new, primary function to send data to your FastAPI backend
  const handleSendMessage = async (messageText = null) => {
    const text = messageText || inputValue.trim();
    if (!text || !patientId) return;

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
      // Make a POST request to your FastAPI backend
      const response = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: text,
          patient_id: patientId,
          session_id: "default"
        })
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const data = await response.json();
      
      // Create response with testing details if available
      let responseText = data.answer;
      
      // Add testing details to response for debugging
      if (data.testing_details) {
        responseText += "\n\n--- TESTING DETAILS ---\n";
        responseText += `Context Retrieved: ${data.testing_details.context_details?.length || 0} items\n`;
        responseText += `Sources: ${data.testing_details.sources_used?.length || 0} sources\n`;
        if (data.testing_details.context_summary) {
          responseText += `Context Summary: ${data.testing_details.context_summary}\n`;
        }
        if (data.testing_details.prompt_sent_to_llm) {
          responseText += `\nPrompt to LLM:\n${data.testing_details.prompt_sent_to_llm}\n`;
        }
        if (data.testing_details.raw_llm_response) {
          responseText += `\nRaw LLM Response:\n${data.testing_details.raw_llm_response}\n`;
        }
      }

      const botResponse = {
        id: Date.now() + 1,
        type: 'bot',
        text: responseText,
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, botResponse]);
    } catch (error) {
      console.error('Error generating response:', error);
      const fallbackResponse = {
        id: Date.now() + 1,
        type: 'bot',
        text: "I'm sorry, I am currently unable to connect to the backend service. Please try again later. Error: " + error.message,
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

  const ConfigPanel = () => (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0,0,0,0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div style={{
        backgroundColor: 'white',
        padding: '2rem',
        borderRadius: '1rem',
        width: '90%',
        maxWidth: '500px',
        maxHeight: '80vh',
        overflow: 'auto'
      }}>
        <h3 style={{ marginTop: 0 }}>Backend Configuration</h3>
        
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Patient ID:
          </label>
          <input
            type="text"
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
            placeholder="e.g., patient-101"
            style={{
              width: '100%',
              padding: '0.5rem',
              border: '1px solid #ccc',
              borderRadius: '0.5rem'
            }}
          />
          <small style={{ color: '#666', fontSize: '0.75rem' }}>
            This ID is used to retrieve specific medical records from your backend.
          </small>
        </div>

        <div style={{ display: 'flex', gap: '1rem' }}>
          <button
            onClick={() => setShowConfig(false)}
            style={{
              flex: 1,
              padding: '0.75rem',
              backgroundColor: '#2196f3',
              color: 'white',
              border: 'none',
              borderRadius: '0.5rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem'
            }}
          >
            <Save style={{ width: '1.25rem', height: '1.25rem' }} /> Save & Close
          </button>
          <button
            onClick={() => setShowConfig(false)}
            style={{
              padding: '0.75rem',
              backgroundColor: '#6b7280',
              color: 'white',
              border: 'none',
              borderRadius: '0.5rem',
              cursor: 'pointer'
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );

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
                Powered by a RAG Backend
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            {/* New Patient ID input field */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label htmlFor="patient-id" style={{ fontSize: '0.875rem', color: '#6b7280', fontWeight: 'bold' }}>Patient ID:</label>
              <input
                id="patient-id"
                type="text"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                placeholder="e.g., patient-101"
                style={{
                  width: '120px',
                  padding: '0.25rem 0.5rem',
                  border: '1px solid #d1d5db',
                  borderRadius: '0.5rem',
                  fontSize: '0.875rem',
                }}
              />
            </div>
            <button
              onClick={() => setShowConfig(true)}
              style={{
                background: '#f3f4f6',
                border: 'none',
                borderRadius: '0.5rem',
                padding: '0.5rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <Settings style={{ width: '1.25rem', height: '1.25rem', color: '#6b7280' }} />
            </button>
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
                <div style={{
                  fontSize: '0.875rem',
                  lineHeight: 1.5,
                  whiteSpace: 'pre-line'
                }}>
                  {message.text}
                </div>
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
          <div style={{
            display: 'flex',
            justifyContent: 'flex-start'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
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
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
              }}>
                <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>
                  MaiBot is typing...
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
        padding: '1rem'
      }}>
        <div style={{
          display: 'flex',
          gap: '0.5rem',
          alignItems: 'flex-end'
        }}>
          <div style={{ flex: 1 }}>
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message here..."
              rows={1}
              style={{
                width: '100%',
                minHeight: '2.5rem',
                maxHeight: '8rem',
                padding: '0.75rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.75rem',
                resize: 'none',
                fontSize: '0.875rem',
                fontFamily: 'inherit',
                lineHeight: 1.5
              }}
            />
          </div>
          <button
            onClick={() => handleSendMessage()}
            disabled={!inputValue.trim() || isTyping}
            style={{
              padding: '0.75rem',
              background: inputValue.trim() && !isTyping ? '#2196f3' : '#9ca3af',
              color: 'white',
              border: 'none',
              borderRadius: '0.75rem',
              cursor: inputValue.trim() && !isTyping ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'background-color 0.2s'
            }}
          >
            <Send style={{ width: '1.25rem', height: '1.25rem' }} />
          </button>
        </div>
      </div>

      {showConfig && <ConfigPanel />}
    </div>
  );
};

export default App;