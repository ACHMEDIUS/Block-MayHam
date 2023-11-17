import sys
import socket
import threading
from turtle import position
import ursina
import json
import random

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from ursina.shaders import lit_with_shadows_shader
from ursina.prefabs.health_bar import HealthBar
from numpy import blackman, floor
from perlin_noise import PerlinNoise

app = Ursina()

window.title = 'Block Mayham'
window.fullscreen = True
window.exit_button.visible = False
window.fps_counter.enabled = False 

Entity.default_shader = lit_with_shadows_shader

menutheme = Audio('assets/Audio/themesing.wav', volume=0.6, loop=True, autoplay=True)
gametheme = Audio('assets/Audio/thememult.wav', volume=0.6, loop=True, autoplay=False)

editor_camera = EditorCamera(enabled=False, ignore_paused=True)

noise = PerlinNoise(octaves=2, seed=786578)
amp = random.randint(1, 3) 
freq = random.randint(10, 20)

#terrain list change Width for performance
shells = []
shellWidth = 26 

#main game with all the nested functions, this is used to call using the main menu
def Singleplayer():
    global Enemy, block, green_bar, gun, shootables_parent, update, genTerr, pause_input, pause_handler, enemies, shoot, input, score, noe, hand
    #enemy class used to spawn multiple enemies    
    class Enemy(Entity):
        def __init__(self, **kwargs):
            super().__init__(parent=shootables_parent, model='assets/objects/sphere.obj', texture='assets/images/sphere2.jpg', scale=0.6, origin_y= -1.5, **kwargs)
            self.health_bar = Entity(parent=self, y=3.8, model='cube', color=color.red, world_scale=(1.5,.1,.1))
            self.collider = SphereCollider(self, center=Vec3(0, 2.5, 0), radius=1)
            self.max_hp = 100
            self.hp = self.max_hp
            
        def update(self):
            global score                  
            dist = distance_xz(block.position, self.position)
            if dist > 1000:
                return

            if dist < 5:
                green_bar.scale_x -= 0.1*time.dt
                if green_bar.scale_x < 0.05:
                    green_bar.scale_x = 0.7
                    score = 0
                    print_on_screen(text='Try again!', position=(0,0), scale=2.5, duration=2)
            
            self.health_bar.alpha = max(0, self.health_bar.alpha - 3*time.dt) 

            self.look_at_2d(block.position, 'y')
            hit_info = raycast(self.world_position + Vec3(0,2,0), self.forward, 30, ignore=(self,))
            if hit_info.entity == block:
                if dist > 4:
                    self.position += self.forward * time.dt * 5                

        @property
        def hp(self):
            return self._hp

        @hp.setter
        def hp(self, value):  
            global score, text      
            self._hp = value
            if value <= 0:
                destroy(self)
                score += 1
                text.y = 1
                text = Text(text=f'Score: {score}', position=Vec2(-0.1, 0.35), scale=2)
                return
                
            self.health_bar.world_scale_x = self.hp / self.max_hp * 1.5
            self.health_bar.alpha = 1

    class Bullet2(ursina.Entity):
        def __init__(self, position: ursina.Vec3, direction: float, x_direction: float, damage: int = random.randint(5, 20), slave=False):
            speed = 69
            dir_rad = ursina.math.radians(direction)
            x_dir_rad = ursina.math.radians(x_direction)

            self.velocity = ursina.Vec3(
                ursina.math.sin(dir_rad) * ursina.math.cos(x_dir_rad),
                ursina.math.sin(x_dir_rad),
                ursina.math.cos(dir_rad) * ursina.math.cos(x_dir_rad)
            ) * speed

            super().__init__(
                position=position + self.velocity / speed,
                model="sphere",
                collider="box",
                color=color.rgb(0, 0, 0),
                scale=0.2
            )

            self.damage = damage
            self.direction = direction
            self.x_direction = x_direction
            self.slave = slave

        def update(self):
            self.position += self.velocity * ursina.time.dt
            hit_info = self.intersects()

            if hit_info.hit:
                ursina.destroy(self)    
    #automatic gun entity
    gun = Entity(model='assets/objects/gun3.obj', color=color.rgb(69, 69, 69), parent=camera, position=(0.95, -0.85, 2), scale=0.16, rotation=(0, -86, 0) , origin_z=-.5, on_cooldown=False)
    gun.muzzle_flash = Entity(parent=gun, position=(8, 5, 0), rotation=(0, 0, 0), scale=1, origin=(0, 0), model='cube', color=color.yellow, enabled=False)
    hand = Entity(model='cube', parent=camera, position=(0.75, -0.4, 0.25), scale=(.3,.2,1), origin_z=-.5, color=color.white, on_cooldown=False)
    shootables_parent = Entity()
    mouse.traverse_target = shootables_parent

    #block enitity with firstperson module as camera and controller(controls)
    block = FirstPersonController(model='cube', texture='white_cube', jump_height=2.5, jump_duration=0.4, origin_y=-2, collider="box",z=-10)
    block.y = 60

    #number of enemies
    noe = random.randint(2, 5)   

    #health bar
    green_bar = Entity(model='quad', parent=camera, position=(0, 0.18, -0.04), scale=(.7,.04,1), color=color.rgb(0, 255, 0), z=0.5)
    
    score=0    
    
    for i in range(shellWidth*shellWidth):
        cube = Entity(model='cube', texture='assets/images/floor.png', collider='box')
        shells.append(cube)
    #infinite terrain function
    def genTerr():
        global amp, freq
        for i in range(len(shells)):
            x = shells[i].x = floor((i/shellWidth) + block.x - 0.5*shellWidth)
            z = shells[i].z = floor((i%shellWidth) + block.z - 0.5*shellWidth)
            y = shells[i].y = floor(noise([x/freq, z/freq])*amp) 

    def update():
        global amp, freq
        genTerr()    
        if block.y < -10:
            block.y = 50   
        if held_keys['escape']:
            quit()       
        if held_keys['shift']:
            block.speed = 8
        else:   
            block.speed = 4
            
    def input(key):
        global b_pos, bullet
        if key == 'space':
            Audio('assets/Audio/jump.wav', loop=False, auto_destroy=True) 
        if key == 'left mouse down':
            shoot()
            b_pos = block.position + ursina.Vec3(0, 2, 0)
            bullet = Bullet2(b_pos, block.world_rotation_y, -block.camera_pivot.world_rotation_x)
            Audio('assets/Audio/gun3.wav', loop=False, delay=1, auto_destroy=True)
        
            
    #game pause menu
    def pause_input(key):        
        if key == 'tab':   
            editor_camera.enabled = not editor_camera.enabled

            block.visible_self = editor_camera.enabled
            block.cursor.enabled = not editor_camera.enabled
            gun.enabled = not editor_camera.enabled
            mouse.locked = not editor_camera.enabled
            editor_camera.position = block.position            

            application.paused = editor_camera.enabled         

    pause_handler = Entity(ignore_paused=True, input=pause_input)

    #infinite enemy generation. if player is alive invoke enemies every 15 seconds
    def enemies():
        for x in range(noe):
            Enemy(x=x*2)
        if green_bar.scale_x > 0.05:
            invoke(enemies, delay=8)

    
    enemies()

    def shoot():
        if not gun.on_cooldown:
            gun.on_cooldown = True
            gun.muzzle_flash.enabled=True
            invoke(gun.muzzle_flash.disable, delay=.05)
            invoke(setattr, gun, 'on_cooldown', False, delay=.15)
            if mouse.hovered_entity and hasattr(mouse.hovered_entity, 'hp'):
                mouse.hovered_entity.hp -= 10
                mouse.hovered_entity.blink(color.red) 

# main menu
class MenuButton(Button):
    def __init__(self, text='', **kwargs):
        super().__init__(text, scale=(.25, .075), highlight_color=color.azure, **kwargs)        

        for key, value in kwargs.items():
            setattr(self, key ,value)


# button_size = (.25, .075)
button_spacing = .075 * 1.25
menu_parent = Entity(parent=camera.ui, y=.15)
main_menu = Entity(parent=menu_parent)
load_menu = Entity(parent=menu_parent)
options_menu = Entity(parent=menu_parent)

state_handler = Animator({
    'main_menu' : main_menu,
    'load_menu' : load_menu,
    'options_menu' : options_menu,
    }
)
def start_single():
    menu_parent.enabled = False
    menutheme.pause()
    Singleplayer()
    gametheme.play()
    
# def start_multi():
#     menu_parent.enabled = False
#     menutheme.pause()
#     Multiplayer()
#     gametheme.play()

#menu buttons
main_menu.buttons = [
    MenuButton('Singleplayer', on_click=Func(start_single)),
    # MenuButton('Multiplayer', on_click=Func(start_multi)),
    MenuButton('Options', on_click=Func(setattr, state_handler, 'state', 'options_menu')),
    MenuButton('Quit', on_click=Sequence(Wait(.01), Func(sys.exit))),
]

for i, e in enumerate(main_menu.buttons):
    e.parent = main_menu
    e.y = (-i-2) * button_spacing

load_menu.back_button = MenuButton(parent=load_menu, text='back', y=((-i-2) * button_spacing), on_click=Func(setattr, state_handler, 'state', 'main_menu'))

#function for audio
volume_slider = Slider(0, 1, default=Audio.volume_multiplier, step=.1, text='Master Volume:', parent=options_menu, x=-.25)

def set_volume_multiplier():
    Audio.volume_multiplier = volume_slider.value
volume_slider.on_value_changed = set_volume_multiplier

#back button
options_back = MenuButton(parent=options_menu, text='Back', x=-.25, origin_x=-.5, on_click=Func(setattr, state_handler, 'state', 'main_menu'))

for i, e in enumerate((volume_slider, options_back)):
    e.y = -i * button_spacing


#animation for menu buttons
for menu in (main_menu, load_menu, options_menu):
    def animate_in_menu(menu=menu):
        for i, e in enumerate(menu.children):
            e.original_x = e.x
            e.x += .1
            e.animate_x(e.original_x, delay=i*.05, duration=.1, curve=curve.out_quad)

            e.alpha = 0
            e.animate('alpha', .7, delay=i*.05, duration=.1, curve=curve.out_quad)

            if hasattr(e, 'text_entity'):
                e.text_entity.alpha = 0
                e.text_entity.animate('alpha', 1, delay=i*.05, duration=.1)

    menu.on_enable = animate_in_menu             

#sun position for shaders
sun = DirectionalLight()
sun.look_at(Vec3(1,-1,-1))
Sky()

app.run()

#multiplayer game functions
# def Multiplayer():
#     global Player2, Enemy2, Bullet2, Network2, n, Floor2, FloorCube2, Wall2, Map2, floor2, receive, update, input, main, player2, prev_pos, prev_dir, enemies2, shoot
    
#     #main player class
#     class Player2(FirstPersonController):
#         def __init__(self, position: ursina.Vec3):
#             super().__init__(
#                 position=position,
#                 model="cube",
#                 texture="white_cube",
#                 jump_height=2.5,
#                 jump_duration=0.4,
#                 origin_y=-2,
#                 collider="box", 
#                 speed=5
#             )
#             self.cursor.color = ursina.color.rgb(255, 0, 0, 122)

#             self.gun = ursina.Entity(
#                 parent=ursina.camera,
#                 position=(0.95, -0.85, 2),
#                 scale=0.16,
#                 rotation=(0, -86, 0),
#                 origin_z=-.5,
#                 model="assets/objects/gun3.obj",
#                 color=color.rgb(69, 69, 69),
#                 on_cooldown=False
#             )
#             self.hand = Entity(
#                 model='cube',
#                 texture='white_cube',
#                 parent=camera, 
#                 position=(0.75, -0.4, 0.25), 
#                 scale=(.3,.2,1), 
#                 origin_z=-.5                 
#             ) 
#             self.healthbar_pos = ursina.Vec2(0, 0.45)
#             self.healthbar_size = ursina.Vec2(0.8, 0.04)
#             self.healthbar_bg = ursina.Entity(
#                 parent=ursina.camera.ui,
#                 model="quad",
#                 color=ursina.color.rgb(255, 0, 0),
#                 position=self.healthbar_pos,
#                 scale=self.healthbar_size
#             )
#             self.healthbar = ursina.Entity(
#                 parent=ursina.camera.ui,
#                 model="quad",
#                 color=ursina.color.rgb(0, 255, 0),
#                 position=self.healthbar_pos,
#                 scale=self.healthbar_size
#             )
#             self.health = 100
#             self.death_message_shown = False

#         def death(self):
#             self.death_message_shown = True

#             ursina.destroy(self.gun)
#             self.rotation = 0
#             self.camera_pivot.world_rotation_x = -45
#             self.world_position = ursina.Vec3(0, 7, -35)
#             self.cursor.color = ursina.color.rgb(0, 0, 0, a=0)

#             ursina.Text(
#                 text="You are dead!",
#                 origin=ursina.Vec2(0, 0),
#                 scale=3
#             )

#         def update(self):
#             self.healthbar.scale_x = self.health / 100 * self.healthbar_size.x

#             if self.health <= 0:
#                 if not self.death_message_shown:
#                     self.death()
#             else:
#                 super().update()

#             if held_keys['shift']:
#                 self.speed=12
#             else:
#                 self.speed=5

#     #enemy class
#     class Enemy2(ursina.Entity):
#         def __init__(self, position: ursina.Vec3, identifier: str, username: str):
#             super().__init__(
#                 position=position,
#                 model="cube",
#                 origin_y=-0.5,
#                 collider="box",
#                 texture="white_cube",
#                 color=ursina.color.color(0, 0, 1),
#                 scale=ursina.Vec3(1, 2, 1)
#             )

#             self.gun = ursina.Entity(
#                 parent=self,
#                 position=ursina.Vec3(.5,-.25,.25),
#                 scale=ursina.Vec3(.3,.2,1),
#                 model="cube",
#                 texture="white_cube",
#                 color=ursina.color.color(0, 0, 0.4)
#             )
            
#             self.hand = Entity(
#                 model='cube',
#                 texture='white_cube',
#                 parent=camera, 
#                 position=(0.7, -0.4, 0.25), 
#                 scale=(.3,.2,1), 
#                 origin_z=-.5, 
#             )

#             self.name_tag = ursina.Text(
#                 parent=self,
#                 text=username,
#                 position=ursina.Vec3(0, 1.3, 0),
#                 scale=ursina.Vec2(5, 3),
#                 billboard=True,
#                 origin=ursina.Vec2(0, 0)
#             )

#             self.health = 100
#             self.id = identifier
#             self.username = username

#         def update(self):
#             try:
#                 color_saturation = 1 - self.health / 100
#             except AttributeError:
#                 self.health = 100
#                 color_saturation = 1 - self.health / 100

#             self.color = ursina.color.color(0, color_saturation, 1)

#             if self.health <= 0:
#                 ursina.destroy(self)

#     #bullet entity class
#     class Bullet2(ursina.Entity):
#         def __init__(self, position: ursina.Vec3, direction: float, x_direction: float, network, damage: int = random.randint(5, 20), slave=False):
#             speed = 60
#             dir_rad = ursina.math.radians(direction)
#             x_dir_rad = ursina.math.radians(x_direction)

#             self.velocity = ursina.Vec3(
#                 ursina.math.sin(dir_rad) * ursina.math.cos(x_dir_rad),
#                 ursina.math.sin(x_dir_rad),
#                 ursina.math.cos(dir_rad) * ursina.math.cos(x_dir_rad)
#             ) * speed

#             super().__init__(
#                 position=position + self.velocity / speed,
#                 model="sphere",
#                 collider="box",
#                 color=color.rgb(0, 0, 0),
#                 scale=0.2
#             )

#             self.damage = damage
#             self.direction = direction
#             self.x_direction = x_direction
#             self.slave = slave
#             self.network = network

#         def update(self):
#             self.position += self.velocity * ursina.time.dt
#             hit_info = self.intersects()

#             if hit_info.hit:
#                 if not self.slave:
#                     for entity in hit_info.entities:
#                         if isinstance(entity, Enemy2):
#                             entity.health -= self.damage
#                             self.network.send_health(entity)

#                 ursina.destroy(self)

#     #network class for validation to server
#     class Network2:
        
#         def __init__(self, server_addr: str, server_port: int, username: str):
#             self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#             self.addr = server_addr
#             self.port = server_port
#             self.username = username
#             self.recv_size = 2048
#             self.id = 0

#         def settimeout(self, value):
#             self.client.settimeout(value)

#         def connect(self):
        
#             self.client.connect((self.addr, self.port))
#             self.id = self.client.recv(self.recv_size).decode("utf8")
#             self.client.send(self.username.encode("utf8"))

#         def receive_info(self):
#             try:
#                 msg = self.client.recv(self.recv_size)
#             except socket.error as e:
#                 print(e)

#             if not msg:
#                 return None

#             msg_decoded = msg.decode("utf8")

#             left_bracket_index = msg_decoded.index("{")
#             right_bracket_index = msg_decoded.index("}") + 1
#             msg_decoded = msg_decoded[left_bracket_index:right_bracket_index]

#             msg_json = json.loads(msg_decoded)

#             return msg_json

#         def send_player(self, player2: Player2):
#             player2_info = {
#                 "object": "player",
#                 "id": self.id,
#                 "position": (player2.world_x, player2.world_y, player2.world_z),
#                 "rotation": player2.rotation_y,
#                 "health": player2.health,
#                 "joined": False,
#                 "left": False
#             }
#             player2_info_encoded = json.dumps(player2_info).encode("utf8")

#             try:
#                 self.client.send(player2_info_encoded)
#             except socket.error as e:
#                 print(e)

#         def send_bullet(self, bullet: Bullet2):
#             bullet_info = {
#                 "object": "bullet",
#                 "position": (bullet.world_x, bullet.world_y, bullet.world_z),
#                 "damage": bullet.damage,
#                 "direction": bullet.direction,
#                 "x_direction": bullet.x_direction
#             }

#             bullet_info_encoded = json.dumps(bullet_info).encode("utf8")

#             try:
#                 self.client.send(bullet_info_encoded)
#             except socket.error as e:
#                 print(e)

#         def send_health(self, player2: Enemy2):
#             health_info = {
#                 "object": "health_update",
#                 "id": player2.id,
#                 "health": player2.health
#             }

#             health_info_encoded = json.dumps(health_info).encode("utf8")

#             try:
#                 self.client.send(health_info_encoded)
#             except socket.error as e:
#                 print(e)
    
    
#     username = 'Block'

#     #validation for server adress
#     while True:

#         #change address to ip for LAN multiplayer
#         server_addr = '127.0.0.1' 
#         server_port = '8000'

#         try:
#             server_port = int(server_port)
#         except ValueError:
#             continue

#         n = Network2(server_addr, server_port, username)
#         n.settimeout(5)

#         error_occurred = False

#         try:
#             n.connect()
#         except ConnectionRefusedError:
#             error_occurred = True
#         except socket.timeout:
#             error_occurred = True
#         except socket.gaierror:
#             error_occurred = True
#         finally:
#             n.settimeout(None)

#         if not error_occurred:
#             break

#     class FloorCube2(ursina.Entity):
#         def __init__(self, position):
#             super().__init__(
#                 position=position,
#                 scale=2,
#                 model="cube",
#                 texture=("assets/images/floor.png"),
#                 collider="box"
#             )
#             self.texture.filtering = None


#     class Floor2:
#         def __init__(self):
#             dark1 = True
#             for z in range(-30, 30, 2):
#                 dark2 = not dark1
#                 for x in range(-30, 30, 2):
#                     cube = FloorCube2(ursina.Vec3(x, 0, z))
#                     if dark2:
#                         cube.color = ursina.color.color(0, 0.2, 0.8)
#                     else:
#                         cube.color = ursina.color.color(0, 0.2, 1)
#                     dark2 = not dark2
#                 dark1 = not dark1


#     class Wall2(ursina.Entity):
#         def __init__(self, position):
#             super().__init__(
#                 position=position,
#                 scale=2,
#                 model="cube",
#                 texture=("assets/images/wall.png"),
#                 origin_y=-0.5
#             )
#             self.texture.filtering = None
#             self.collider = ursina.BoxCollider(self, size=ursina.Vec3(1, 2, 1))

#     class Map2:
#         def __init__(self):
#             for y in range(1, 4, 2):
#                 Wall2(ursina.Vec3(6, y, 0))
#                 Wall2(ursina.Vec3(6, y, 2))
#                 Wall2(ursina.Vec3(6, y, 4))
#                 Wall2(ursina.Vec3(6, y, 6))
#                 Wall2(ursina.Vec3(6, y, 8))

#                 Wall2(ursina.Vec3(4, y, 8))
#                 Wall2(ursina.Vec3(2, y, 8))
#                 Wall2(ursina.Vec3(0, y, 8))
#                 Wall2(ursina.Vec3(-2, y, 8))

#                 Wall2(ursina.Vec3(-6, y, 0))
#                 Wall2(ursina.Vec3(-6, y, 2))
#                 Wall2(ursina.Vec3(-6, y, 4))
#                 Wall2(ursina.Vec3(-6, y, 6))
#                 Wall2(ursina.Vec3(-6, y, 8))

#                 Wall2(ursina.Vec3(16, y, 0))
#                 Wall2(ursina.Vec3(16, y, 2))
#                 Wall2(ursina.Vec3(16, y, 4))
#                 Wall2(ursina.Vec3(16, y, 6))
#                 Wall2(ursina.Vec3(16, y, 8))

#                 Wall2(ursina.Vec3(4, y, 8))
#                 Wall2(ursina.Vec3(2, y, 8))
#                 Wall2(ursina.Vec3(0, y, 8))
#                 Wall2(ursina.Vec3(-2, y, 8))

#                 Wall2(ursina.Vec3(-26, y, 0))
#                 Wall2(ursina.Vec3(-26, y, 2))
#                 Wall2(ursina.Vec3(-26, y, 4))
#                 Wall2(ursina.Vec3(-26, y, 6))
#                 Wall2(ursina.Vec3(-26, y, 8))

#                 Wall2(ursina.Vec3(6, y, 12))
#                 Wall2(ursina.Vec3(6, y, 14))
#                 Wall2(ursina.Vec3(6, y, 16))
#                 Wall2(ursina.Vec3(6, y, 18))
#                 Wall2(ursina.Vec3(6, y, 20))

#                 Wall2(ursina.Vec3(16, y, 16))
#                 Wall2(ursina.Vec3(5, y, 5))
#                 Wall2(ursina.Vec3(-5, y, -5))
#                 Wall2(ursina.Vec3(10, y, -3))

#                 Wall2(ursina.Vec3(-26, y, 20))
#                 Wall2(ursina.Vec3(-24, y, 20))
#                 Wall2(ursina.Vec3(-22, y, 20))
#                 Wall2(ursina.Vec3(-20, y, 20))
#                 Wall2(ursina.Vec3(-18, y, 20))

#                 Wall2(ursina.Vec3(16, y, 8))
#                 Wall2(ursina.Vec3(18, y, 8))
#                 Wall2(ursina.Vec3(20, y, 8))
#                 Wall2(ursina.Vec3(22, y, 8))
#                 Wall2(ursina.Vec3(24, y, 8))

#                 Wall2(ursina.Vec3(0, y, -10))
#                 Wall2(ursina.Vec3(-2, y, -10))
#                 Wall2(ursina.Vec3(-4, y, -10))
#                 Wall2(ursina.Vec3(-6, y, -10))

#                 Wall2(ursina.Vec3(-26, y, -20))
#                 Wall2(ursina.Vec3(-24, y, -20))
#                 Wall2(ursina.Vec3(-22, y, -20))
#                 Wall2(ursina.Vec3(-20, y, -20))
#                 Wall2(ursina.Vec3(-18, y, -20))


#     floor2 = Floor2()
#     Map2()

#     player2 = Player2(ursina.Vec3(0, 1, 0))
#     prev_pos = player2.world_position
#     prev_dir = player2.world_rotation_y
#     enemies2 = []
#     def receive():
#         while True:
#             try:
#                 info = n.receive_info()
#             except Exception as e:
#                 print(e)
#                 continue

#             if not info:
#                 sys.exit()

#             if info["object"] == "player2":
#                 enemy_id = info["id"]

#                 if info["joined"]:
#                     new_enemy = Enemy2(ursina.Vec3(*info["position"]), enemy_id, info["username"])
#                     new_enemy.health = info["health"]
#                     enemies2.append(new_enemy)
#                     continue

#                 enemy = None

#                 for e in enemies2:
#                     if e.id == enemy_id:
#                         enemy = e
#                         break

#                 if not enemy:
#                     continue

#                 if info["left"]:
#                     enemies2.remove(enemy)
#                     ursina.destroy(enemy)
#                     continue

#                 enemy.world_position = ursina.Vec3(*info["position"])
#                 enemy.rotation_y = info["rotation"]

#             elif info["object"] == "bullet":
#                 b_pos = ursina.Vec3(*info["position"])
#                 b_dir = info["direction"]
#                 b_x_dir = info["x_direction"]
#                 b_damage = info["damage"]
#                 new_bullet = Bullet2(b_pos, b_dir, b_x_dir, n, b_damage, slave=True)
#                 ursina.destroy(new_bullet, delay=2)

#             elif info["object"] == "health_update":
#                 enemy_id = info["id"]

#                 enemy = None

#                 if enemy_id == n.id:
#                     enemy = player2
#                 else:
#                     for e in enemies2:
#                         if e.id == enemy_id:
#                             enemy = e
#                             break

#                 if not enemy:
#                     continue

#                 enemy.health = info["health"]
    
#     player2.gun.muzzle_flash = Entity(parent=player2.gun, position=(8, 5, 0), rotation=(0, 0, 0), scale=1, origin=(0, 0), model='cube', color=color.yellow, enabled=False)
#     shootables_parent = Entity()
#     mouse.traverse_target = shootables_parent

#     def update():
#         if player2.health > 0:
#             global prev_pos, prev_dir

#             if prev_pos != player2.world_position or prev_dir != player2.world_rotation_y:
#                 n.send_player(player2)

#             prev_pos = player2.world_position
#             prev_dir = player2.world_rotation_y

#         if player2.y < -10:
#             player2.y = 60 

#     def shoot():
#         if not player2.gun.on_cooldown:
#             player2.gun.on_cooldown = True
#             player2.gun.muzzle_flash.enabled=True
#             invoke(player2.gun.muzzle_flash.disable, delay=.05)
#             invoke(setattr, player2.gun, 'on_cooldown', False, delay=.15)
#             if mouse.hovered_entity and hasattr(mouse.hovered_entity, 'hp'):
#                 mouse.hovered_entity.hp -= 10
#                 mouse.hovered_entity.blink(color.red)   

#     def input(key):
#         if key == "left mouse down" and player2.health > 0:
#             b_pos = player2.position + ursina.Vec3(0, 2, 0)
#             bullet = Bullet2(b_pos, player2.world_rotation_y, -player2.camera_pivot.world_rotation_x, n)
#             n.send_bullet(bullet)
#             shoot()
#             ursina.destroy(bullet, delay=2)
#             Audio('assets/Audio/gun3.wav', loop=False, delay=1)
#         if held_keys['escape']:
#             quit()
#         if key == 'space':
#             Audio('assets/Audio/jump.wav', loop=False)

#     def main():
#         msg_thread = threading.Thread(target=receive, daemon=True)
#         msg_thread.start()


#     if __name__ == "__main__":
#         main()
