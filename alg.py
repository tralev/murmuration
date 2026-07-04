import pygame
import random
import math

# Настройки экрана
WIDTH, HEIGHT = 1000, 700
FPS = 60

# Настройки стаи (Боидов)
NUM_BOIDS = 150        # Количество птиц (можно увеличить, если компьютер мощный)
BOID_SIZE = 3          # Размер птицы на экране
MAX_SPEED = 4          # Максимальная скорость
MAX_FORCE = 0.1        # Насколько резко птица может менять направление

# Радиусы чувствительности
VISUAL_RANGE = 70      # Расстояние, на котором птицы видят друг друга
SEPARATION_RANGE = 20  # Расстояние, ближе которого начинается паника и разлет

class Boid:
    def __init__(self):
        # Случайное появление на экране
        self.position = pygame.Vector2(random.uniform(0, WIDTH), random.uniform(0, HEIGHT))
        # Случайное направление движения
        angle = random.uniform(0, 2 * math.pi)
        self.velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * random.uniform(2, MAX_SPEED)
        self.acceleration = pygame.Vector2(0, 0)

    def update(self):
        # Обновляем скорость и позицию
        self.velocity += self.acceleration
        if self.velocity.length() > MAX_SPEED:
            self.velocity.scale_to_length(MAX_SPEED)
        self.position += self.velocity
        # Сбрасываем ускорение для следующего кадра
        self.acceleration *= 0

        # Телепортация при вылете за границы экрана (эффект бесконечного неба)
        if self.position.x > WIDTH: self.position.x = 0
        elif self.position.x < 0: self.position.x = WIDTH
        if self.position.y > HEIGHT: self.position.y = 0
        elif self.position.y < 0: self.position.y = HEIGHT

    def apply_force(self, force):
        self.acceleration += force

    def flock(self, boids):
        # Три основных правила Рейнольдса
        separation = pygame.Vector2(0, 0)
        alignment = pygame.Vector2(0, 0)
        cohesion = pygame.Vector2(0, 0)

        total_neighbors = 0
        total_too_close = 0

        for other in boids:
            if other is self:
                continue

            distance = self.position.distance_to(other.position)

            # Если птица в зоне видимости
            if distance < VISUAL_RANGE:
                alignment += other.velocity
                cohesion += other.position
                total_neighbors += 1

                # Если птица слишком близко (угроза столкновения)
                if distance < SEPARATION_RANGE:
                    # Сила направлена в противоположную сторону от соседа
                    diff = self.position - other.position
                    if distance > 0:
                        diff /= distance  # Вес зависит от близости
                    separation += diff
                    total_too_close += 1

        # Вычисляем финальные силы
        if total_neighbors > 0:
            alignment /= total_neighbors
            if alignment.length() > 0:
                alignment.scale_to_length(MAX_SPEED)
            alignment -= self.velocity
            if alignment.length() > MAX_FORCE:
                alignment.scale_to_length(MAX_FORCE)

            cohesion /= total_neighbors
            cohesion -= self.position
            if cohesion.length() > 0:
                cohesion.scale_to_length(MAX_SPEED)
            cohesion -= self.velocity
            if cohesion.length() > MAX_FORCE:
                cohesion.scale_to_length(MAX_FORCE)

        if total_too_close > 0:
            separation /= total_too_close
            if separation.length() > 0:
                separation.scale_to_length(MAX_SPEED)
            separation -= self.velocity
            if separation.length() > MAX_FORCE:
                separation.scale_to_length(MAX_FORCE)

        # Применяем силы с коэффициентами (весом) для баланса
        self.apply_force(separation * 1.5)
        self.apply_force(alignment * 1.0)
        self.apply_force(cohesion * 1.0)

    def draw(self, screen):
        # Рисуем птицу в виде кружка (или треугольника)
        pygame.draw.circle(screen, (220, 220, 240), (int(self.position.x), int(self.position.y)), BOID_SIZE)

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Симуляция мурмурации (Boids)")
    clock = pygame.time.Clock()

    # Создаем стаю
    flock = [Boid() for _ in range(NUM_BOIDS)]

    running = True
    while running:
        clock.tick(FPS)
        screen.fill((25, 25, 35))  # Темный цвет неба

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Обновляем и рисуем птиц
        for boid in flock:
            boid.flock(flock)
            boid.update()
            boid.draw(screen)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
