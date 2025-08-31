// Control-Observador para RC-RC-RC

// ******************************************************** //
//                                                          //
// Control por asignación de polos para circuito RC-RC-RC   //
//                                                          //
// Abril 29 del 2025, MAPG, EAG                             //
//                                                          //
//                                                          //
// ******************************************************** //


// ******************************************************** //
//----------  Constantes  --------//                        //
// ******************************************************** //

//---------- Definición Pines IO analogicos--------//                  
  #define pR 0                // pin de referencia             
  #define pX1 1               // pin de estado 1   
  #define pX2 2               // pin de estado 2      
  #define pX3 3               // pin de estado 3                       
  #define pU 5               // pin de salida de control (entrada a planta)  

//---------- Definición Pines IO discretos--------//                  
  #define pLED_ENABLE 9             // LED 8  
  #define pArranque 2              // SW 2                                     
  #define pParo 3              // SW 3     

//---------- Escalamientos para analogicas de 0 a 5 V --------//
  #define mX 0.004882813      // Pendiente 0-1023 -> 0 - 5
  #define bX 0                // Ajuste cero para 0-1023 -> 0 - 5
  #define mU 51               // Pendiente 0 - 5 -> 0 - 1023
  #define bU 0                // Ajuste cero 0 - 5 -> 0 - 1023


// ******************************************************** //
//----------  Variables globales  --------//                //
// ******************************************************** //

//---------- Ganancias de Controlador --------//
  float Kp = 5;
  float K1 = 1;
  float K2 = -3;
  float K3 = 6;
  
//---------- Ganancias de Observador --------//
  float H1 = 536;
  float H2 = 194;
  float H3 = 25;

//---------- Tiempo --------//
  unsigned long TS_code = 0;  // Tiempo que tarda programa
  unsigned long TIC = 0;      // Estampa de tiempo inicio ciclos
  unsigned long TC = 0;       // Faltante para TS
   
//----------  Señales --------//
  float R = 0;                // Referencia
  float Y = 0;                // Salida
  float X1 = 0;               // Estado 1
  float X2 = 0;               // Estado 2
  float X3 = 0;               // Estado 3
  float U = 0;                // Salida control
  int Ui = 0;                 // Salida control tarjeta 

//----------  Observador --------//

//-- Estados obs --//
  float XeR1 = 0;             // Estado estimado 1 en k, Xe1[k]
  float XeR2 = 0;             // Estado estimado 2 en k, Xe2[k]
  float XeR3 = 0;             // Estado estimado 3 en k, Xe3[k]

//-- Modelo obs --//
  // Matriz A
  float Am11 = -2;
  float Am12 = 1;
  float Am13 = 0;  
  float Am21 = 1;
  float Am22 = -2;
  float Am23 = 1;
  float Am31 = 0;
  float Am32 = 1;
  float Am33 = -1;    
  // Matriz B
  float Bm1 = 1;
  float Bm2 = 0;  
  float Bm3 = 0;   
  // Matriz C
  float Cm1 = 0;
  float Cm2 = 0;  
  float Cm3 = 1;  
  
//---------- Otros --------//
  bool Habilitado = 0;        // Señal {0,1} para entradas escalón                        
  unsigned long TS = 50;      // Muestreo TS miliseg        //
  float Tseg = 0.05;          // Muestreo en Tseg segundos  //
// ******************************************************** //
  
  #include <SoftwareSerial.h>

// ******************************************************** //
//----------  Rutinia de inicio --------                   //
// ******************************************************** //

void setup() {
    //--Inicia serial--//
  Serial.begin(9600);

  //--Configura pines digitales--//  
  pinMode(2, INPUT);
  pinMode(3, INPUT);
  pinMode(8, OUTPUT);
  pinMode(9, OUTPUT);
}

// ******************************************************** //
//---------- Rutinia principal  --------//                  //
// ******************************************************** //

void loop() {                     
  proc_entradas();                    // Procesamiento de Entradas
  observador();                       // Observador
  control();                          // Control
  proc_salidas();                     // Procesado de Salidas
  //coms_arduino_ide();                 // Comunicaciones
  coms_python(&R,&Y,&U);
  espera();
}

// ******************************************************** //
//---------- Rutinias de control y observador--------       //                          
// ******************************************************** //


//-- Control --//
void control(){
  // Ley de control
    U = Kp*R - K1*X1 - K2*X2 - K3*X3;       // Ley de control retro estado estimado
   
  // Saturacion
  if(U >= 5.0) U = 5.0;               // Saturacion de control en rango 0 a 5V                      
  else if(U < 0) U = 0;
}


//-- Observador para estimar X1 --//
void observador(){
  // Dinamica observador
  float f1 = Am11*XeR1 + Am12*XeR2 + Am13*XeR3 + Bm1*U + H1*(Y-(Cm1*XeR1 + Cm2*XeR2 + Cm3*XeR3));     // Dinamica estado 1 observador
  float f2 = Am21*XeR1 + Am22*XeR2 + Am23*XeR3 + Bm2*U + H2*(Y-(Cm1*XeR1 + Cm2*XeR2 + Cm3*XeR3));     // Dinamica estado 2 observador
  float f3 = Am31*XeR1 + Am32*XeR2 + Am33*XeR3 + Bm3*U + H3*(Y-(Cm1*XeR1 + Cm2*XeR2 + Cm3*XeR3));     // Dinamica estado 3 observador
  
  // Integracion Euler
  float XeN1 = XeR1 + Tseg*f1;              // Integrador estado 1 mediante Euler
  float XeN2 = XeR2 + Tseg*f2;              // Integrador estado 2 mediante Euler
  float XeN3 = XeR3 + Tseg*f3;              // Integrador estado 2 mediante Euler
  XeR1 = XeN1;
  XeR2 = XeN2;
  XeR3 = XeN3;
  
  // Los estados del observador no ocupan saturación porque están en float
}

// ******************************************************** //
//---------- Rutinias de IO y control de tiempo     --------//                          
// ******************************************************** //

//-- Procesado de entradas --//
void proc_entradas(){
  // No se ocupa leer X1 (Vc1) porque se estima con observador
  X1 = analogRead(pX1)*mX+bX;            // Lectura de salida de planta en pin pX3
  X2 = analogRead(pX2)*mX+bX;               // Lectura de salida de planta en pin pX2
  X3 = analogRead(pX3)*mX+bX;               // Lectura de salida de planta en pin pX2
  escalon();                                // Genera un escalon en Habilitado con SW2 y SW3.
  R = Habilitado*(analogRead(pR)*mX+bX);    // Lectura de referencia en pin pR, Habilitado = {0,1} es para escalones
  Y = X3;
}


//-- Procesado de salidas --//
void proc_salidas(){
  Ui = int(U*mU+bU);                    // Escalamiento
  analogWrite(pU, Ui);                  // Salida PWM en pin pU
}


//-- Memoria {0,1} para entrada escalón --//
void escalon(){
  
  if(digitalRead(pArranque) == 1) Habilitado = 1;      // Memoria on/off en Habilitado
  else if(digitalRead(pParo) == 1) Habilitado = 0; // Set con SW2. Reset con SW3

  if(Habilitado == 1) digitalWrite(pLED_ENABLE,HIGH);            // Led blink en LED8
  else digitalWrite(pLED_ENABLE, LOW);                           // Cuando Habilitado = 1

}

//-- Para muestreo uniforme --//
void espera(){   
  TS_code = millis()- TIC;                 // Tiempo de ciclo
  TC = TS - TS_code;                       // Calcula altante para TS
  if (TS_code < TS) delay(TC);             // Espera para completar ciclo de TS   
  TIC = millis();
}

//-- Comunicación con monitor --//
void coms_arduino_ide(){  
  Serial.print("y_d(t):");            // Referencia
  Serial.print(R);                    // Referencia
  Serial.print(",");                  // Separador     
  Serial.print("y(t):");              // Salida
  Serial.println(Y);                  // Salida (terminar con "serial.println")
}

void coms_python(float* Rp, float* Yp, float* Up)
{
  byte* byteData1 = (byte*)(Rp);
  byte* byteData2 = (byte*)(Yp);
  byte* byteData3 = (byte*)(Up);
  byte buf[12] = {byteData1[0], byteData1[1], byteData1[2], byteData1[3],
                 byteData2[0], byteData2[1], byteData2[2], byteData2[3],
                 byteData3[0], byteData3[1], byteData3[2], byteData3[3]};
  Serial.write(buf, 12);
}
