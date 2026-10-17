# adapter outbound: whatsapp

`WhatsAppCloudSender` implementa el puerto `MessageSender` sobre WhatsApp Cloud API (Graph API de Meta, ADR 0014): envía textos y marca los mensajes como leídos con el indicador de escritura. Solo usa la biblioteca estándar. Los errores de Meta se traducen a `ChannelDeliveryError` con su código, sin el número ni el texto.
